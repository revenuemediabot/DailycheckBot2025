import os
import sys
import time
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class ProcessLock:
    """Кроссплатформенная блокировка процесса"""
    
    def __init__(self, lockfile: str):
        self.lockfile = Path(lockfile)
        self.fp: Optional[any] = None
        self.pid: Optional[int] = None
        
        # Создаём директорию для lock файла
        self.lockfile.parent.mkdir(exist_ok=True, parents=True)
    
    def acquire(self) -> bool:
        """Захватывает блокировку"""
        try:
            if sys.platform == "win32":
                return self._acquire_windows()
            else:
                return self._acquire_unix()
        except Exception as e:
            logger.error(f"Ошибка захвата блокировки: {e}")
            return False
    
    def _acquire_unix(self) -> bool:
        """Захват блокировки на Unix-системах (Linux, macOS)"""
        try:
            import fcntl
            
            # Проверяем существующую блокировку
            if self.lockfile.exists():
                if not self._check_existing_lock():
                    return False
            
            # Создаём новую блокировку
            self.fp = open(self.lockfile, "w")
            fcntl.flock(self.fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # Записываем PID
            self.pid = os.getpid()
            self.fp.write(str(self.pid))
            self.fp.flush()
            
            logger.info(f"Блокировка захвачена (PID: {self.pid})")
            return True
            
        except (IOError, OSError) as e:
            logger.warning(f"Не удалось захватить блокировку: {e}")
            if self.fp:
                self.fp.close()
                self.fp = None
            return False
    
    def _acquire_windows(self) -> bool:
        """Захват блокировки на Windows"""
        try:
            # Проверяем существующую блокировку
            if self.lockfile.exists():
                if not self._check_existing_lock():
                    return False
            
            # Создаём блокировку через эксклюзивный доступ к файлу
            self.fp = open(self.lockfile, "w")
            
            # Записываем PID
            self.pid = os.getpid()
            self.fp.write(str(self.pid))
            self.fp.flush()
            
            logger.info(f"Блокировка захвачена (PID: {self.pid})")
            return True
            
        except (IOError, OSError) as e:
            logger.warning(f"Не удалось захватить блокировку: {e}")
            if self.fp:
                self.fp.close()
                self.fp = None
            return False
    
    def _check_existing_lock(self) -> bool:
        """Проверяет, активна ли существующая блокировка"""
        try:
            with open(self.lockfile, "r") as f:
                existing_pid = int(f.read().strip())
            
            # Проверяем, запущен ли процесс
            if self._is_process_running(existing_pid):
                logger.warning(f"Бот уже запущен (PID: {existing_pid})")
                return False
            else:
                logger.info(f"Удаляем устаревшую блокировку (PID: {existing_pid})")
                self.lockfile.unlink()
                return True
                
        except (ValueError, FileNotFoundError):
            # Некорректный или отсутствующий файл блокировки
            if self.lockfile.exists():
                self.lockfile.unlink()
            return True
    
    def _is_process_running(self, pid: int) -> bool:
        """Проверяет, запущен ли процесс с указанным PID"""
        try:
            if sys.platform == "win32":
                import subprocess
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}"],
                    capture_output=True,
                    text=True
                )
                return str(pid) in result.stdout
            else:
                # Unix-системы
                os.kill(pid, 0)  # Отправляем сигнал 0 (проверка существования)
                return True
        except (OSError, subprocess.SubprocessError, ImportError):
            return False
    
    def release(self):
        """Освобождает блокировку"""
        try:
            if self.fp:
                if sys.platform != "win32":
                    try:
                        import fcntl
                        fcntl.flock(self.fp, fcntl.LOCK_UN)
                    except ImportError:
                        pass
                
                self.fp.close()
                self.fp = None
            
            # Удаляем файл блокировки
            if self.lockfile.exists():
                self.lockfile.unlink()
            
            logger.info(f"Блокировка освобождена (PID: {self.pid})")
            
        except Exception as e:
            logger.error(f"Ошибка освобождения блокировки: {e}")
    
    def __enter__(self):
        """Поддержка context manager"""
        if self.acquire():
            return self
        else:
            raise RuntimeError("Не удалось захватить блокировку")
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Поддержка context manager"""
        self.release()
    
    def __del__(self):
        """Автоматическое освобождение при удалении объекта"""
        self.release()

def ensure_single_instance(lockfile: str) -> ProcessLock:
    """
    Гарантирует, что запущен только один экземпляр приложения
    
    Args:
        lockfile: Путь к файлу блокировки
        
    Returns:
        ProcessLock объект
        
    Raises:
        SystemExit: Если не удалось захватить блокировку
    """
    lock = ProcessLock(lockfile)
    
    if not lock.acquire():
        logger.error("❌ Приложение уже запущено!")
        print("❌ Приложение уже запущено! Завершите существующий процесс.")
        sys.exit(1)
    
    return lock
