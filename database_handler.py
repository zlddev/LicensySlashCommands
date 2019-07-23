import aiosqlite
from pathlib import Path
from helpers import licence_generator


class DatabaseHandler:
    DB_PATH = "databases/"
    DB_EXTENSION = ".sqlite3"

    @classmethod
    async def create(cls, db_name: str = "main", db_backup_prefix: str = "backup"):
        """"
        Can't use await in __init__ so we create a factory pattern.
        To correctly create this object you need to call :
            await DatabaseHandler.create()

        """
        self = DatabaseHandler()
        self.db_name = db_name
        self.db_backup_prefix = db_backup_prefix
        self.connection = await self._get_connection()
        return self

    def __init__(self):
        self.db_name = None
        self.db_backup_prefix = None
        self.connection = None

    async def _get_connection(self) -> aiosqlite.core.Connection:
        """
        Returs a connection to the db, if db doesn't exist create new
        :return: aiosqlite.core.Connection
        """
        path = DatabaseHandler._construct_path(self.db_name)
        if Path(path).is_file():
            conn = await aiosqlite.connect(path)
            return conn
        else:
            print("Database not found! Creating fresh ...")
            return await DatabaseHandler._create_database(path)

    @staticmethod
    async def _create_database(path: str) -> aiosqlite.core.Connection:
        """
        :param path: path where database will be created, including file name and extension
        :return: aiosqlite.core.Connection
        """
        conn = await aiosqlite.connect(path)
        await conn.execute("CREATE TABLE GUILDS "
                           "("
                           "GUILD_ID TEXT PRIMARY KEY, "
                           "PREFIX TEXT CHECK(PREFIX IS NULL OR LENGTH(PREFIX) <= 3), "
                           "ENABLE_LOG_CHANNEL TINYINT DEFAULT 0, "
                           "LOG_CHANNEL_ID TEXT, "
                           "ENABLE_JOIN_ROLE TINYINT DEFAULT 0, "
                           "JOIN_ROLE_ID TEXT, "
                           "DEFAULT_LICENSE_ROLE_ID TEXT, "
                           "DEFAULT_LICENSE_DURATION_HOURS UNSIGNED BIG INT DEFAULT 720"
                           ")"
                           )

        await conn.execute("CREATE TABLE LICENSED_MEMBERS "
                           "("
                           "MEMBER_ID TEXT, "
                           "GUILD_ID TEXT, "
                           "EXPIRATION_DATE DATE, "
                           "LICENSED_ROLE_ID TEXT, "
                           "UNIQUE(MEMBER_ID, GUILD_ID)"
                           ")"
                           )

        await conn.execute("CREATE TABLE GUILD_LICENSES "
                           "("
                           "LICENSE TEXT PRIMARY KEY, "
                           "GUILD_ID TEXT, "
                           "LICENSED_ROLE_ID TEXT, "
                           "UNIQUE(LICENSE, GUILD_ID)"
                           ")"
                           )

        await conn.commit()
        print("Database successfully created!")
        return conn

    @staticmethod
    def _construct_path(db_name: str) -> str:
        return DatabaseHandler.DB_PATH + db_name + DatabaseHandler.DB_EXTENSION

    async def drop_guild_license(self, license: str, guild_id: int):
        """
        Called when member has redeemed license.
        The license is deleted from table GUILD_LICENSES
        :param license: license to delete
        :param guild_id:

        TODO: is guild_id necessary since license is unique?

        """
        delete_query = "DELETE FROM GUILD_LICENSES WHERE LICENSE=? AND GUILD_ID=?"
        await self.connection.execute(delete_query, (license, guild_id))
        await self.connection.commit()

    async def generate_guild_licenses(self, number: int, guild_id: int, default_license_role_id: int) -> list:
        """
        :param number: number of licenses to generate
        :param guild_id:
        :param default_license_role_id: role to link to the license
        :return: list of all generated licenses

        TODO: Use positive_number type hint

        TODO: is guild_id necessary since license is unique?

        """
        licenses = licence_generator.generate(number)
        query = "INSERT INTO GUILD_LICENSES(LICENSE, GUILD_ID, LICENSED_ROLE_ID) VALUES(?,?,?)"
        for license in licenses:
            await self.connection.execute(query, (license, guild_id, default_license_role_id))
        await self.connection.commit()
        return licenses

    async def get_default_guild_license_role_id(self, guild_id: int) -> int:
        """
        Gets the default license role id from specific guild.
        This role will be used as link when no role argument is passed in 'generate' command
        :return: int default license role id
        """
        query = "SELECT DEFAULT_LICENSE_ROLE_ID FROM GUILDS WHERE GUILD_ID=?"
        async with self.connection.execute(query, (guild_id,)) as cursor:
            row = await cursor.fetchone()
            return int(row[0])

    async def get_license_role_id(self, license: str) -> int:
        """
        Returns licensed role id that the param license is linked to
        :param license: license the role is linked to
        :return: int license role id

        """
        query = "SELECT LICENSED_ROLE_ID FROM GUILD_LICENSES WHERE LICENSE=?"
        async with self.connection.execute(query, (license,)) as cursor:
            row = await cursor.fetchone()
            return int(row[0])

    async def get_guild_licenses(self, number: int, guild_id: int, license_role_id: int) -> list:
        """
        Returns list of licenses that are linked to license_role_id role.
        :param number: max number of licenses to return
        :param guild_id:
        :param license_role_id: we get only those licenses that are linked to this role id
        :return: list of licenses

         TODO: is guild_id necessary since license is unique?
        """
        licenses = []
        query = "SELECT LICENSE FROM GUILD_LICENSES WHERE GUILD_ID=? AND LICENSED_ROLE_ID=? LIMIT ?"
        async with self.connection.execute(query, (guild_id, license_role_id, number)) as cursor:
            rows = await cursor.fetchall()
            # rows format:
            # [('license1',), ('license2',)]
            for row in rows:
                licenses.append(row[0])

        return licenses