try:
    import MySQLdb  # noqa: F401  (use mysqlclient if the project switches to it)
except ImportError:  # Pragmatic default: PyMySQL is pure Python and Windows-friendly.
    import pymysql

    pymysql.install_as_MySQLdb()
