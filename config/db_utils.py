# config/db_utils.py
import os
import subprocess
import re
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
import logging
from dotenv import load_dotenv
load_dotenv()  # Загружаем .env для config

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Константы
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MY_PGDATA = os.path.join(SCRIPT_DIR, "..", "pgdata")  # Папка для pgserver в корне проекта
SALT_SIZE = 16
NONCE_SIZE = 12

# Глобальные переменные
engine = None
Session = None
using_pgserver = False
db = None
current_db_info = ""
current_port = 5432  # Дефолтный порт

config = {
    'local_user': 'postgres',
    'local_password': '',
    'pgserver_password': ''
}

def _derive_key(password: str, salt: bytes) -> bytes:
    """PBKDF2 → 256‑битный ключ AES."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600_000,
    )
    return kdf.derive(password.encode())

def encrypt_password(plain: str) -> str:
    """Возвращает base64‑строку: salt||nonce||ciphertext||tag."""
    import os, base64
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key = _derive_key('123', salt)  # ADMIN_PASSWORD из оригинала
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plain.encode(), None)
    blob = salt + nonce + ct
    return base64.b64encode(blob).decode()

def decrypt_password(blob_b64: str) -> str:
    """Обратное преобразование."""
    import base64
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    blob = base64.b64decode(blob_b64)
    if len(blob) < SALT_SIZE + NONCE_SIZE:
        raise ValueError("Повреждённые данные")
    salt = blob[:SALT_SIZE]
    nonce = blob[SALT_SIZE:SALT_SIZE + NONCE_SIZE]
    ct = blob[SALT_SIZE + NONCE_SIZE:]
    key = _derive_key('123', salt)
    aesgcm = AESGCM(key)
    plain = aesgcm.decrypt(nonce, ct, None)
    return plain.decode()

def try_local_postgres():
    """Пытается подключиться к локальному PostgreSQL."""
    global engine, Session, using_pgserver, current_db_info, current_port
    # Используем config из .env напрямую
    local_user = config['local_user'] or os.getenv('DB_USERNAME', 'postgres')
    local_password = config['local_password'] or os.getenv('DB_PASS', '')
    local_uri = f"postgresql://{local_user}:{local_password}@localhost:5432/{os.getenv('DB_NAME', 'postgres')}"

    try:
        subprocess.check_output(['psql', '--version'], stderr=subprocess.DEVNULL)
        logger.info("PostgreSQL установлен на ПК.")

        engine_local = create_engine(
            local_uri,
            connect_args={'options': '-c timezone=3'}
        )
        SessionLocal = sessionmaker(bind=engine_local)

        session = SessionLocal()
        result = session.execute(text("SELECT 1;")).scalar()
        if result == 1:
            logger.info("Успешное подключение к локальному PostgreSQL.")
            engine = engine_local
            Session = SessionLocal
            using_pgserver = False
            current_db_info = "подключен локальный PostgreSQL port:5432"
            current_port = 5432
            session.close()
            return True

    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.info("PostgreSQL не установлен на ПК (psql не найден).")
    except OperationalError as e:
        if "connection refused" in str(e).lower() or "does not exist" in str(e).lower():
            logger.info("Локальный PostgreSQL не запущен.")
        else:
            logger.error(f"Ошибка подключения к локальному PostgreSQL: {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка с локальным PostgreSQL: {e}")

    if 'session' in locals():
        session.close()
    if 'engine_local' in locals():
        engine_local.dispose()
    return False
    
def setup_pgserver():
    """Настраивает pgserver."""
    global engine, Session, using_pgserver, db, current_db_info, current_port
    config['pgserver_password'] = os.getenv('PGSERVER_PASSWORD', 'postgres')  # Дефолт
    try:
        import pgserver
    except ImportError:
        logger.error("pgserver не установлен. Установите: pip install pgserver")
        return False

    db = pgserver.get_server(MY_PGDATA)
    db_uri_no_pass = db.get_uri()
    logger.info(f"Запускаем pgserver. URI без пароля: {db_uri_no_pass}")

    port_match = re.search(r':(\d+)/', db_uri_no_pass)
    port = port_match.group(1) if port_match else "неизвестно"
    current_port = int(port) if port_match else 5432

    engine_no_pass = create_engine(db_uri_no_pass, connect_args={'options': '-c timezone=3'})
    SessionNoPass = sessionmaker(bind=engine_no_pass)

    password_set = False
    try:
        session = SessionNoPass()
        session.execute(text(f"ALTER USER postgres PASSWORD '{config['pgserver_password']}'"))
        session.commit()
        logger.info("Пароль установлен в pgserver.")
        password_set = True
        session.close()
        engine_no_pass.dispose()
    except OperationalError as e:
        if "no password supplied" in str(e):
            logger.info("Пароль уже требуется в pgserver.")
        else:
            logger.error(f"Ошибка в pgserver: {e}")
            return False
    finally:
        if 'session' in locals():
            session.close()
        if 'engine_no_pass' in locals():
            engine_no_pass.dispose()

    db_uri_with_pass = db_uri_no_pass.replace('postgres:@', f"postgres:{config['pgserver_password']}@")

    engine_pg = create_engine(db_uri_with_pass, connect_args={'options': '-c timezone=3'})
    SessionPg = sessionmaker(bind=engine_pg)

    try:
        session = SessionPg()
        session.close()
        engine = engine_pg
        Session = SessionPg
        using_pgserver = True
        current_db_info = f"подключен pgserver port:{port}"
        return True
    except OperationalError as e:
        logger.error(f"Ошибка подключения в pgserver: {e}")
        return False

def start_db():
    """Запускает БД (pgserver или локальный)."""
    global engine, Session, current_db_info
    if engine:
        logger.info("БД уже запущена.")
        return True
    if try_local_postgres():
        logger.info("Используем локальный PostgreSQL")
        return True
    else:
        if not setup_pgserver():
            logger.error("Ошибка запуска БД")
            return False
        logger.info("Используем pgserver")
        return True

def stop_db():
    """Останавливает pgserver."""
    global db, using_pgserver, engine, Session, current_db_info
    if using_pgserver and db:
        try:
            db.cleanup()
            logger.info("pgserver остановлен.")
        except Exception as e:
            logger.error(f"Ошибка остановки pgserver: {e}")
        finally:
            using_pgserver = False
            db = None
            current_db_info = ""
            if engine:
                engine.dispose()
                engine = None
            Session = None

def get_db_session():
    """Возвращает сессию БД."""
    global Session
    if Session:
        from sqlalchemy.orm import sessionmaker
        return Session()
    return None

def get_django_databases():
    """Возвращает DATABASES dict для Django на основе текущего состояния БД."""
    start_db()  # Принудительный вызов, если не запущено
    if using_pgserver:
        return {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'postgres',
            'USER': 'postgres',
            'PASSWORD': config['pgserver_password'],
            'HOST': 'localhost',
            'PORT': current_port,
            'OPTIONS': {
                'options': '-c search_path=rcdm -c timezone=0',  # Фикс timezone (UTC offset)
                'client_encoding': 'UTF8',
            },
        }
    elif engine:
        return {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'postgres'),
            'USER': config['local_user'],
            'PASSWORD': config['local_password'],
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': int(os.getenv('DB_PORT', 5432)),
            'OPTIONS': {
                'options': '-c search_path=rcdm -c timezone=0',  # Фикс timezone (UTC offset)
                'client_encoding': 'UTF8',
            },
        }
    return None  # Fallback to SQLite