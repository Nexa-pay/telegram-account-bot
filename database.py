import asyncpg
from datetime import datetime
from typing import Optional, List, Dict

class Database:
    def __init__(self, dsn):
        self.dsn = dsn
        self.pool = None

    async def connect(self):
        """Create connection pool"""
        self.pool = await asyncpg.create_pool(self.dsn)

    async def close(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()

    async def init_db(self):
        """Initialize database tables"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS telegram_accounts (
                    id SERIAL PRIMARY KEY,
                    phone_number VARCHAR(20) UNIQUE NOT NULL,
                    session_string TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT true,
                    added_by BIGINT NOT NULL,
                    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reports_count INTEGER DEFAULT 0
                );
                
                CREATE INDEX IF NOT EXISTS idx_phone_number ON telegram_accounts(phone_number);
                CREATE INDEX IF NOT EXISTS idx_is_active ON telegram_accounts(is_active);
            ''')

    async def add_account(self, phone_number: str, session_string: str, added_by: int) -> int:
        """Add new account to database"""
        async with self.pool.acquire() as conn:
            result = await conn.execute('''
                INSERT INTO telegram_accounts (phone_number, session_string, added_by)
                VALUES ($1, $2, $3)
                ON CONFLICT (phone_number) DO UPDATE 
                SET session_string = EXCLUDED.session_string,
                    added_date = CURRENT_TIMESTAMP
                RETURNING id
            ''', phone_number, session_string, added_by)
            
            # Parse the result to get the ID
            return int(result.split()[-1]) if result else None

    async def get_accounts(self, active_only: bool = False) -> List[Dict]:
        """Get all accounts"""
        async with self.pool.acquire() as conn:
            if active_only:
                rows = await conn.fetch('''
                    SELECT * FROM telegram_accounts 
                    WHERE is_active = true 
                    ORDER BY added_date DESC
                ''')
            else:
                rows = await conn.fetch('''
                    SELECT * FROM telegram_accounts 
                    ORDER BY added_date DESC
                ''')
            
            return [dict(row) for row in rows]

    async def get_account(self, account_id: int) -> Optional[Dict]:
        """Get single account by ID"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow('''
                SELECT * FROM telegram_accounts WHERE id = $1
            ''', account_id)
            return dict(row) if row else None

    async def update_account_status(self, account_id: int, is_active: bool) -> bool:
        """Update account active status"""
        async with self.pool.acquire() as conn:
            result = await conn.execute('''
                UPDATE telegram_accounts 
                SET is_active = $1 
                WHERE id = $2
            ''', is_active, account_id)
            return result == "UPDATE 1"

    async def increment_reports(self, account_id: int) -> bool:
        """Increment reports count for an account"""
        async with self.pool.acquire() as conn:
            result = await conn.execute('''
                UPDATE telegram_accounts 
                SET reports_count = reports_count + 1 
                WHERE id = $1
            ''', account_id)
            return result == "UPDATE 1"

    async def delete_account(self, account_id: int) -> bool:
        """Delete account from database"""
        async with self.pool.acquire() as conn:
            result = await conn.execute('''
                DELETE FROM telegram_accounts WHERE id = $1
            ''', account_id)
            return result == "DELETE 1"

    async def get_stats(self) -> Dict:
        """Get account statistics"""
        async with self.pool.acquire() as conn:
            total = await conn.fetchval('SELECT COUNT(*) FROM telegram_accounts')
            active = await conn.fetchval('SELECT COUNT(*) FROM telegram_accounts WHERE is_active = true')
            return {
                'total': total,
                'active': active,
                'inactive': total - active
            }