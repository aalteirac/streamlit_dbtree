from pathlib import Path
from typing import Optional
import json
import streamlit as st
import streamlit.components.v1 as components
import threading
import time
import snowflake.connector


frontend_dir = (Path(__file__).parent / "frontend").absolute()
_component_func = components.declare_component(
	"streamlit_dbtree", path=str(frontend_dir)
)

class RunQueryThread (threading.Thread):
    def __init__(self, connection,sql,tables):
        threading.Thread.__init__(self)
        self.connection = connection
        self.tables=tables
        self.sql=sql
        self.end=False

    def run(self):  
        tables=run_sql(self.connection, self.sql, True)
        for table in tables:
            name = table[1]
            info = {'name': name}
            self.tables.append(info)    
        self.end = True   

class QueryThread (threading.Thread):
    def __init__(self, connection,dbo,qtype):
        threading.Thread.__init__(self)
        self.connection = connection
        self.qtype=qtype
        self.dbo=dbo
        self.end=False

    def run(self):  
        if(self.qtype=="sc"):                     
            get_database_schemas(self.connection,self.dbo)
        if(self.qtype=="tb"):                     
            get_database_tables(self.connection,self.dbo)   
        if(self.qtype=="vs"):                     
            get_database_views(self.connection,self.dbo) 
        self.end = True     

def run_sql(conn, sql, fetchall):
    cur = conn.cursor()
    try:
        cur.execute(sql)
        if fetchall:
            res = cur.fetchall()
        else:
            res = cur.fetchone()

    except snowflake.connector.errors.ProgrammingError as e:
        print("Statement error: {0}".format(e.msg))
        res = ('Statement error: ' + str(e.msg),)
    except:
        print("Unexpected error: {0}".format(e.msg))

    finally:
        cur.close()
    return res

def get_database_list(conn):
    database_objects = []
    sql = 'show databases'
    databases = run_sql(conn, sql, True)

    for database in databases:
        name = database[1]
        database_objects.append({"name":name})
    
    allSCThread=[]
    for db in database_objects:
        sc=QueryThread(conn,[db],"sc")
        sc.start()
        allSCThread.append(sc)
    while any(it.end ==False for it in allSCThread):
        time.sleep(0.001)    
    allOtherThread=[]  
    for db in database_objects:
        tb=QueryThread(conn,[db],"tb")
        tb.start()
        vs=QueryThread(conn,[db],"vs")
        vs.start()  
        allOtherThread.append(tb)
        allOtherThread.append(vs)
    while any(it.end ==False for it in allOtherThread):
        time.sleep(0.001)  
    # one=get_database_tables_threaded(conn,database_objects)  
    # two=get_database_views_threaded(conn,database_objects)
    # all=one+two
    # while any(it.end ==False for it in all):
    #     time.sleep(0.001)    
    return database_objects

def get_database_schemas(conn, database_objects):
    for db in database_objects:
        sql = 'show schemas in database ' + db["name"]
        schemas = run_sql(conn, sql, True)
        db["schema"]=[]
        for schema in schemas:
            db_info = {}
            name = schema[1]
            # if name != "INFORMATION_SCHEMA":
            info = {'name': name}
            db["schema"].append(info)

    return database_objects

def get_database_tables_threaded(conn, database_objects):
    allTableThread=[]
    for db in database_objects:
        for sc in db["schema"]:
            sql = "show tables in"+' '+ db["name"]+"."+sc["name"]+";"
            sc["tables"]=[]
            tt=RunQueryThread(conn,sql,sc["tables"])
            tt.start()
            allTableThread.append(tt)    
    return allTableThread

def get_database_views_threaded(conn, database_objects):
    allViewThread=[]
    for db in database_objects:
        for sc in db["schema"]:
            sql = "show views in"+' '+ db["name"]+"."+sc["name"]+";"
            sc["views"]=[]
            tt=RunQueryThread(conn,sql,sc["views"])
            tt.start()         
    return allViewThread

def get_database_tables(conn, database_objects):
    for db in database_objects:
        for sc in db["schema"]:
            sql = "show tables in"+' '+ db["name"]+"."+sc["name"]+";"
            sc["tables"]=[]
            tables = run_sql(conn, sql, True)
            for table in tables:
                name = table[1]
                info = {'name': name}
                sc["tables"].append(info) 
    return database_objects

def get_database_views(conn, database_objects):
    for db in database_objects:
        for sc in db["schema"]:
            sql = "show views in"+' '+ db["name"]+"."+sc["name"]+";"
            views = run_sql(conn, sql, True)
            sc["views"]=[]
            for v in views:
                name = v[1]
                info = {'name': name}
                sc["views"].append(info) 
    return database_objects

# @st.cache(suppress_st_warning=True,hash_funcs={snowflake.connector.connection.SnowflakeConnection:lambda _: None})
def getAll(conn):
    return get_database_list(conn) 

def streamlit_dbtree(
    conn,
    key: Optional[str] = None,
    backgroundColor:Optional[str] = "transparent",
    showBorder:Optional[bool] = False,
    selectColor:Optional[str] = "#208fb7",
    hoverColor:Optional[str] = "#e5e5e5",
    fontColor:Optional[str] = "grey",
    fontSelectedColor:Optional[str] = "white",
    height:Optional[int] = 200,
):
    if st.session_state.get("alldbinfo") is None:
        res=  getAll(conn)
        st.session_state["alldbinfo"]=res
    component_value = _component_func(
        data=json.dumps(st.session_state["alldbinfo"]),key=key,showBorder=showBorder,fontSelectedColor=fontSelectedColor,backgroundColor=backgroundColor,fontColor=fontColor,height=height,selectColor=selectColor,hoverColor=hoverColor
    )

    return component_value



