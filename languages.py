from config import language

translations = {
    'ENG': {'create_new_record_crl_hash': 'New DB record created',
            'cant_download_crl': 'Error download CRL %(url)s: %(download_error)s',
            'bad_crl': 'Bad CRL url %(url)s',
            'crl_successfully_installed': 'CRL successfully installed %(crl_file_hash)s (%(installation_info)s)',
            'crl_error_installed': 'Error CRL installation %(crl_file_hash)s (%(installation_info)s)',
            'installing_crl': 'Install CRL %(crl_wait_file)s'},
    'RUS': {'create_new_record_crl_hash': 'Создана новая запись в БД',
            'cant_download_crl': 'Ошибка загрузки CRL %(url)s: %(download_error)s',
            'bad_crl': 'Некорректная ссылка на CRL %(url)s',
            'crl_successfully_installed': 'CRL успешно установлен %(crl_file_hash)s (%(installation_info)s)',
            'crl_error_installed': 'Ошибка установки CRL %(crl_file_hash)s (%(installation_info)s)',
            'installing_crl': 'Установка CRL %(crl_wait_file)s'}}


def log_add(key):
    return ' '.join(['''%(subjKeyId)s # ''', str(translations[language][key])])

