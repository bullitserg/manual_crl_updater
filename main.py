import argparse
import requests
import hashlib
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from shutil import move
from multiprocessing.dummy import Pool as ThreadPool
from os.path import normpath, join, isfile, exists
from os import remove, mkdir, listdir
from itertools import count
from time import sleep
from datetime import datetime
from ets.ets_mysql_lib import MysqlConnection as Mc
from ets.ets_certmanager_logs_parser_v2 import install_crl
from queries import *
from config import *
from logger_module import *
from languages import *

PROGNAME = 'Manual CRL updater'
DESCRIPTION = '''Скрипт для обновления дополнительных CRL'''
VERSION = '1.0'
AUTHOR = 'Belim S.'
RELEASE_DATE = '2018-11-11'

wait_install_crl_dir = 'wait_install_crl'
actual_crl_dir = 'actual_crl'
bad_crl_dir = 'bad_crl'
old_crl_dir = 'old_crl'
tmp_crl_dir = 'tmp_crl'
tmp_crl_name = 'tmp.crl'


# def install_crl(server, crl_file, **kwargs):
#     """Тестовая функция установки crl"""
#     return True, None


def show_version():
    """Функция показа версии программы"""
    print(PROGNAME, VERSION, '\n', DESCRIPTION, '\nAuthor:', AUTHOR, '\nRelease date:', RELEASE_DATE)


def create_parser():
    """Функция-обработчик параметров командной строки"""

    parser = argparse.ArgumentParser(description=DESCRIPTION)

    parser.add_argument('-v', '--version', action='store_true',
                        help="Показать версию программы")

    parser.add_argument('-s', '--server', type=int, choices=server_list,
                        help="Установить номер сервера")
    return parser

# парсим аргументы командной строки
my_parser = create_parser()
namespace = my_parser.parse_args()


def get_datetime_stamp_for_file():
    """Функция получения строки даты для имени crl"""
    return datetime.now().strftime('%Y%m%d_%H%M%S') + '_'


def get_datetime_stamp_for_dir():
    """Функция получения строки даты для названия текущего дня"""
    return datetime.now().strftime('%Y%m%d')


def get_crl_file(info):
    """Функция загрузки crl файла"""

    # получаем полный путь до загружаемого файла
    crl_tmp_file_location = join(tmp_crl_dir, info['subjKeyId'] + '.crl')

    # удаляем файл, если он уже существует
    if isfile(crl_tmp_file_location):
        remove(crl_tmp_file_location)

    # если ссылка не заканчивается .crl, то ссылка кривая
    if not str(info['url']).endswith('.crl'):
        logger.info(log_add('bad_crl') % info)
        info['crl_tmp_file'] = None
        info['is_download'] = False
        return info['crl_tmp_file']

    # пробуем загрузить файл по ссылке
    try:
        response = requests.get(info['url'], timeout=(download_wait_timeout, None), verify=False)
        if response.status_code == 200:
            crl_data = response.content
            # записываем данные в файл
            with open(crl_tmp_file_location, mode='wb') as crl_out_f:
                crl_out_f.write(crl_data)

        info['crl_tmp_file'] = crl_tmp_file_location

    # обрабатываем исключения с логированием
    except requests.exceptions.ReadTimeout:
        info['download_error'] = 'Read timeout'
        logger.info(log_add('cant_download_crl') % info)
        info['is_download'] = False
        info['crl_tmp_file'] = None

    except requests.exceptions.ConnectTimeout:
        info['download_error'] = 'Connect timeout'
        logger.info(log_add('cant_download_crl') % info)
        info['is_download'] = False
        info['crl_tmp_file'] = None

    except Exception as crl_err:
        info['download_error'] = crl_err
        logger.info(log_add('cant_download_crl') % info)
        info['is_download'] = False
        info['crl_tmp_file'] = None

    info['is_download'] = True
    return info['crl_tmp_file']


def get_crl_db_hash(info):
    """Функция для получения хэша последнего установленного crl по данному сертификату"""
    # пробуем получить хэш и локейшен прежнего crl
    crl_hash_data = cn_crl.execute_query(get_crl_hash_query % info, dicted=True)
    # если нашлись, то добавляем их в словарь
    if crl_hash_data:
        info.update(crl_hash_data[0])
    # если не нашлись, то добавляем новую запись в базу и логируем
    else:
        cn_crl.execute_query(insert_crl_hash_query % info)
        info['crl_db_hash'] = None
        info['crl_location'] = None
        logger.info(log_add('create_new_record_crl_hash') % info)
    # вернем найденный хэш
    return info['crl_db_hash']


def get_crl_file_hash(info):
    """функция получения хэша нового файла crl"""
    # если файла нет, то укажем что хэш также не определен
    if not isfile(info['crl_tmp_file']):
        info['crl_file_hash'] = None
        return info['crl_file_hash']

    # если файл найден, то посчитаем хэш по первым 8192 байтам
    with open(info['crl_tmp_file'], mode='rb') as crl_file_o:
        crl_file_d = crl_file_o.read(8192)
        m = hashlib.sha1()
        m.update(crl_file_d)
        info['crl_file_hash'] = m.hexdigest()

    return info['crl_file_hash']


def install_crl_l(info):
    """Функция для установки CRL"""
    log_add('installing_crl') % info
    # инициируем счетчик попыток установки
    crl_counter = count(start=crl_install_tries, step=-1)
    # в installation_info пишутся сведения о статусе каждой установки
    installation_info = []
    # устанавливаем crl необходимое количество раз
    while next(crl_counter):
        crl_install_status, crl_install_error = install_crl(info['server'], info['crl_wait_file'],
                                                            is_local=False, test_mode=test_mode)

        installation_info.append('OK' if crl_install_status else str(crl_install_error))
        sleep(install_timeout)

    # пишем в словарь строку статусов всех установок
    info['installation_info'] = ', '.join(installation_info)

    # если была хоть одна успешная попытка установки, то указываем что все ок
    if 'OK' in installation_info:
        # собираем путь с именем для crl
        info['crl_actual_file'] = join(actual_crl_dir,
                                       info['subjKeyId'] + '.crl')

        # если существует актуальный файл, то переносим его
        if exists(info['crl_actual_file']):

            # создаем директорию за текущий день если она отсутствует
            crl_old_dir_with_date = join(old_crl_dir, get_datetime_stamp_for_dir())
            if not exists(crl_old_dir_with_date):
                mkdir(crl_old_dir_with_date)

            # получаем расположение файла
            info['crl_old_file'] = join(crl_old_dir_with_date,
                                        get_datetime_stamp_for_file() + info['subjKeyId'] + '.crl')

            # переносим файл в директорию архива
            move(info['crl_actual_file'], info['crl_old_file'])

        # перемещаем новый установленный crl в директорию актуальных crl
        try:
            move(info['crl_wait_file'], info['crl_actual_file'])
        except FileNotFoundError:
            pass

        # логируем
        logger.info(log_add('crl_successfully_installed') % info)
        # возвращаем метку успешной установки

        return True

    # если отсутствуют успешные установки
    else:
        # собираем путь с именем для crl
        # создаем директорию за текущий день если она отсутствует
        bad_crl_dir_with_date = join(bad_crl_dir, get_datetime_stamp_for_dir())
        if not exists(bad_crl_dir_with_date):
            mkdir(bad_crl_dir_with_date)

        info['crl_bad_file'] = join(bad_crl_dir_with_date,
                                    get_datetime_stamp_for_file() + info['subjKeyId'] + '.crl')

        # перемещаем проблемный crl
        move(info['crl_wait_file'], info['crl_bad_file'])

        logger.info(log_add('crl_error_installed') % info)
        return False


def check_for_install(crl_info):
    """Функция для проверки необходимости установки crl"""

    crl_info['server'] = namespace.server
    get_crl_db_hash(crl_info)

    # если указанный crl скачать не получилось, то ставим метку в базу и переходим к следующей записи
    if not crl_info['is_download']:
        cn_crl.execute_query(update_set_download_fail_query % crl_info)
        return
    
    # если указанный crl отсутствует, то переходим к следующей записи
    if not crl_info['crl_tmp_file']:
        return

    # добавляем в crl_info хэш crl
    get_crl_file_hash(crl_info)

    # если хэши одинаковые, то переходим к следующей записи, а сам crl нам больше не нужен
    if crl_info['crl_db_hash'] == crl_info['crl_file_hash']:
        try:
            remove(crl_info['crl_tmp_file'])
        except FileNotFoundError:
            pass
        return

    # собираем путь с именем для crl и переносим его в директорию ожидания установки
    crl_info['crl_wait_file'] = join(wait_install_crl_dir,
                                     crl_info['subjKeyId'] + '.crl')

    # переносим для установки, а если такого нет - значит его уже установили ранее
    # в этом случае нам нужно взять хэш из базы, иначе установится повторно
    try:
        move(crl_info['crl_tmp_file'], crl_info['crl_wait_file'])
        crl_for_update.append(crl_info)
    except FileNotFoundError:

        crl_info['crl_file_hash'] = crl_info['crl_db_hash']
    return


if __name__ == '__main__':

    # выводим версию и выходим, если установлен version
    if namespace.version:
        show_version()
        exit(0)

    # если указан сервер, то запускаемся как сервис
    if namespace.server:
        try:
            # инициируем лог-файл
            log_file = join(normpath(log_dir), log_name_mask % namespace.server)
            init_log_config(log_file)
            logger_name = 'SERVER_%s' % namespace.server
            logger = logger(logger_name)
            logger.info('Starting (server %s, waiting %s)' % (namespace.server, sleep_time))

            # отключаем варнинги по ssh
            requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

            # проверяем наличие основной рабочей директории crl_dir
            crl_dir = normpath(crl_dir_template % namespace.server)
            if not exists(crl_dir):
                raise Exception('Отсутствует директория %s' % crl_dir)

            # при необходимости создаем все необходимые поддиректории
            actual_crl_dir = normpath(join(crl_dir, actual_crl_dir))
            old_crl_dir = normpath(join(crl_dir, old_crl_dir))
            bad_crl_dir = normpath(join(crl_dir, bad_crl_dir))
            tmp_crl_dir = normpath(join(crl_dir, tmp_crl_dir))
            wait_install_crl_dir = normpath(join(crl_dir, wait_install_crl_dir))

            for location in bad_crl_dir, actual_crl_dir, old_crl_dir, tmp_crl_dir, wait_install_crl_dir:
                if not exists(location):
                    mkdir(location)

            # перед запуском удаляем содержимое tmp_crl_dir, wait_install_crl_dir
            for location in tmp_crl_dir, wait_install_crl_dir:
                for f in [join(location, file) for file in listdir(location) if file.endswith('.crl')]:
                    remove(f)

            # подключаемся к базе сертификатов
            cn_crl = Mc(connection=Mc.MS_CERT_INFO_CONNECT)
            cn_crl.connect()

            # основной рабочий цикл
            while True:
                # получаем сведения о crl из бд
                manual_crl_info = cn_crl.execute_query(get_manual_crl_info_query, dicted=True)

                # загружаем crl в несколько потоков
                pool = ThreadPool(download_threads_count)
                pool.map(get_crl_file, manual_crl_info)
                pool.close()
                pool.join()

                # проверяем каждый скачанный crl на необходимость установки и добавляем его в crl_for_update
                crl_for_update = []
                for c_info in manual_crl_info:
                    check_for_install(c_info)

                # устанавливаем каждый crl предназначенный для установки
                for c in crl_for_update:
                    # если установили crl, то пишем данные о нем в базу
                    if install_crl_l(c):
                        cn_crl.execute_query(update_crl_hash_query_ok % c)
                    else:
                        cn_crl.execute_query(update_crl_hash_query_bad % c)

                # задержка перед следующим запуском
                sleep(sleep_time)

        # если при исполнении будут исключения - кратко выводим на терминал, остальное - в лог
        except Exception as e:
            logger.fatal('Fatal error! Exit', exc_info=True)
            print('Critical error: %s' % e)
            print('More information in log file')
            exit(1)
    else:
        show_version()
        print('For more information run use --help')
exit(0)

