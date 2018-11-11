crl_dir_template = 'C:/%s'                                                  # рабочая директория
log_dir = 'C:/Users/belim/PycharmProjects/Accredited CRL updater/'          # директория для хранения логов

log_name_mask = 'crl_cert_installer_%s.log'                                 # маска для названия файла лога

test_mode = True                                                            # включение тестового режима (без установки)
language = 'ENG'                                                            # выбор языка при логировании
server_list = [1, 2, 4, 5]                                                  # доступные сервера
sleep_time = 0                                                              # время задержки выполнения, seconds

crl_install_tries = 3                                                       # количество попыток установки CRL
install_timeout = 0                                                         # время задержки между установками
download_wait_timeout = 1                                                   # время задержки загрузки в каждом потоке (не меньше 0)
download_threads_count = 4                                                  # количество потоков загрузки
