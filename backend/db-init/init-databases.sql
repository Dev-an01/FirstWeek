-- Initialize databases for FirstWeek services
-- This script runs automatically when PostgreSQL container starts for the first time

-- Create firstweek_chat database for chat-service if it doesn't exist
SELECT 'CREATE DATABASE firstweek_chat'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'firstweek_chat')\gexec

-- Note: avatar_user_db is created automatically by POSTGRES_DB env variable

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE firstweek_chat TO postgres;
GRANT ALL PRIVILEGES ON DATABASE avatar_user_db TO postgres;
