"""
Utilidades para conexión y manejo de base de datos PostgreSQL
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
import os
import logging
from typing import Optional, Dict, List, Any
from contextlib import contextmanager
from config.settings import Config

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manejador de conexiones a PostgreSQL"""
    
    def __init__(self):
        self.pool: Optional[SimpleConnectionPool] = None
        self.database_url = Config.DATABASE_URL
        
    def init_db(self):
        """Inicializar pool de conexiones"""
        try:
            # Configurar pool más conservador para evitar problemas SSL
            self.pool = SimpleConnectionPool(
                minconn=2,
                maxconn=10,  # Pool más pequeño para evitar saturación
                dsn=self.database_url
            )
            logger.info("✅ Pool de conexiones PostgreSQL inicializado (2-10 conexiones)")
            return True
        except Exception as e:
            logger.error(f"❌ Error inicializando base de datos: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """Context manager para obtener conexión del pool con retry logic"""
        if not self.pool:
            raise Exception("Base de datos no inicializada")
        
        conn = None
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                conn = self.pool.getconn()
                # Verificar que la conexión esté viva
                with conn.cursor() as test_cursor:
                    test_cursor.execute("SELECT 1")
                yield conn
                break
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                error_msg = str(e).lower()
                if "ssl connection has been closed" in error_msg:
                    logger.warning(f"⚠️ Error SSL de conexión (intento {retry_count + 1}/{max_retries}): Conexión SSL cerrada inesperadamente")
                else:
                    logger.warning(f"⚠️ Error de conexión (intento {retry_count + 1}/{max_retries}): {e}")
                
                if conn:
                    try:
                        self.pool.putconn(conn, close=True)  # Cerrar conexión defectuosa
                    except:
                        pass
                    conn = None
                
                retry_count += 1
                if retry_count >= max_retries:
                    logger.error("❌ Máximo de reintentos alcanzado para conexión de BD")
                    raise e
                
                # Esperar más tiempo para errores SSL
                import time
                time.sleep(1.0)  # Esperar 1 segundo entre reintentos
            except Exception as e:
                if conn:
                    conn.rollback()
                raise e
            finally:
                if conn:
                    self.pool.putconn(conn)
    
    def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Ejecutar query SELECT y retornar resultados"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
    
    def execute_insert(self, query: str, params: tuple = None) -> bool:
        """Ejecutar INSERT y retornar éxito"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                conn.commit()
                return True
    
    def execute_update(self, query: str, params: tuple = None) -> int:
        """Ejecutar UPDATE/DELETE y retornar filas afectadas"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                conn.commit()
                return cursor.rowcount
    
    def check_connection(self) -> bool:
        """Verificar conectividad de base de datos"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    return True
        except Exception as e:
            logger.error(f"❌ Error verificando conexión: {e}")
            return False

# Instancia global del manejador
db_manager = DatabaseManager()

def init_db():
    """Inicializar base de datos"""
    return db_manager.init_db()

def get_db_manager() -> DatabaseManager:
    """Obtener instancia del manejador de BD"""
    return db_manager 