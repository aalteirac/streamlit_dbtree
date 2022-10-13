
import snowflake.connector
import re
import threading
import time


class QueryThread (threading.Thread):
    def __init__(self, connection,dbo,qtype):
        threading.Thread.__init__(self)
        self.connection = connection
        self.qtype=qtype
        self.dbo=dbo
        self.result=[]
        self.end=False

    def run(self):  
        if(self.qtype=="sc"):                     
            get_database_schemas(self.connection,self.dbo)
        if(self.qtype=="tb"):                     
            get_database_tables(self.connection,self.dbo)   
        if(self.qtype=="vs"):                     
            get_database_views(self.connection,self.dbo) 
        self.end = True     


def show_verbose(verbose, text_to_print):
    if verbose:
        print(text_to_print)
    return


# run_sql to pass result set back
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

def get_database_tables(conn, database_objects):
    for db in database_objects:
        for sc in db["schema"]:
            sql = "show tables in"+' '+ db["name"]+"."+sc["name"]+";"
            tables = run_sql(conn, sql, True)
            sc["tables"]=[]
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

def get_database_udfs(conn, database_objects, verbose, just_schema, objf, ignoreshare):
    print('--Step 8.   Getting UDF List')
    # Loop through all the databases, or a single database and populate the stages.
    for db in database_objects.keys():
        if just_schema:
            sql = 'use database ' + db
            sqloutput = run_sql(conn, sql, False)
            sql = 'show USER functions in schema ' + just_schema
        else:
            sql = 'show USER functions in database ' + db
        show_verbose(verbose, sql)
        udfs = run_sql(conn, sql, True)

        for udf in udfs:
            db_info = {}
            role_obj = {}

            name = udf[1]
            schema = udf[2]
            comment = ''
            created_on = udf[0]
            secure = udf[13]
            argument_signature = udf[8]
            argument_signature = argument_signature[argument_signature.find('('):argument_signature.find(')') + 1]

            sql = 'select function_owner , argument_signature from ' + db + ".INFORMATION_SCHEMA.FUNCTIONS where function_name = '" + name + "' and function_catalog = '" + db + "' and function_schema = '" + schema + "'"
            show_verbose(verbose, sql)
            owner_tup = run_sql(conn, sql, False)
            role_owner = owner_tup[0]
            # Old way of doing it, now changed in the metadata  2019-08-15 fix
            # #argument_signature = owner_tup[1]

            if schema != 'INFORMATION_SCHEMA':
                sql = "select get_ddl('FUNCTION', '" + db + '.' + schema + '.' + name + argument_signature + "')"
                show_verbose(verbose, sql)
                ddl_tup = run_sql(conn, sql, False)
                ddl = ddl_tup[0]
                # ddl = 'USE SCHEMA ' + schema + ';\n '+ ddl

                if ddl[0:9] != 'Statement':
                    grants_list = get_grants_on_object(conn, 'FUNCTION',
                                                       db + '.' + schema + '.' + name + argument_signature, verbose,
                                                       objf, ignoreshare)
                else:
                    grants_list = [
                        'Error getting ' + "select get_ddl('FUNCTION', '" + db + '.' + schema + '.' + name + argument_signature + "')"]

                info = {'NAME': name, 'CREATED': created_on, 'OWNER': role_owner, 'COMMENT': comment, 'SCHEMA': schema,
                        'DDL': ddl, 'SECURE': secure, 'GRANTS': grants_list}
                db_info['08-UDFS'] = info

                role_obj = database_objects[db]

                if role_owner in role_obj:
                    role_obj[role_owner].append(db_info)
                else:
                    role_obj[role_owner] = []
                    role_obj[role_owner].append(db_info)

                database_objects[db] = role_obj

    return database_objects


def get_database_procedures(conn, database_objects, verbose, just_schema, objf, ignoreshare):
    print('--Step 9.   Getting Procedure List')
    # Loop through all the databases, or a single database and populate the stages.
    for db in database_objects.keys():
        if just_schema:
            sql = 'use database ' + db
            sqloutput = run_sql(conn, sql, False)
            sql = 'show procedures in schema ' + just_schema
        else:
            sql = 'show procedures in database ' + db
        show_verbose(verbose, sql)
        procs = run_sql(conn, sql, True)

        for proc in procs:
            db_info = {}
            role_obj = {}

            name = proc[1]
            schema = proc[2]
            comment = ''
            created_on = proc[0]
            secure = proc[13]
            proc_arguments = proc[8]
            # Find the first ) for the closing paren for the Arguments list.
            name_argument_signature = proc_arguments[0:proc_arguments.find(')') + 1]

            # get the ownership role
            sql = 'show grants on PROCEDURE ' + db + '.' + schema + '.' + name_argument_signature
            show_verbose(verbose, sql)
            results = run_sql(conn, sql, True)
            # sql='select * from table(result_scan(last_query_id())) where "privilege"='+"'OWNERSHIP'"
            # results = run_sql(conn, sql, False)

            role_owner = 'PUBLIC --Please check this is correct'
            for result in results:
                if result[1] == 'OWNERSHIP':
                    role_owner = result[5]

            sql = "select get_ddl('PROCEDURE', '" + db + '.' + schema + '.' + name_argument_signature + "')"
            show_verbose(verbose, sql)
            ddl_tup = run_sql(conn, sql, False)
            ddl = ddl_tup[0]

            grants_list = get_grants_on_object(conn, 'PROCEDURE', db + '.' + schema + '.' + name_argument_signature,
                                               verbose, objf, ignoreshare)

            info = {'NAME': name, 'CREATED': created_on, 'OWNER': role_owner, 'COMMENT': comment, 'SCHEMA': schema,
                    'DDL': ddl, 'SECURE': secure, 'GRANTS': grants_list}
            db_info['09-PROCEDURES'] = info

            role_obj = database_objects[db]

            if role_owner in role_obj:
                role_obj[role_owner].append(db_info)
            else:
                role_obj[role_owner] = []
                role_obj[role_owner].append(db_info)

            database_objects[db] = role_obj

    return database_objects


def get_database_pipes(conn, database_objects, verbose, just_schema, objf, ignoreshare):
    print('--Step 10.  Getting Pipe List')
    # Loop through all the databases, or a single database and populate the stages.
    for db in database_objects.keys():
        if just_schema:
            sql = 'use database ' + db
            sqloutput = run_sql(conn, sql, False)
            sql = 'show pipes in schema ' + just_schema
        else:
            sql = 'show pipes in database ' + db
        show_verbose(verbose, sql)
        pipes = run_sql(conn, sql, True)

        for pipe in pipes:
            db_info = {}
            role_obj = {}

            name = pipe[1]
            schema = pipe[3]
            role_owner = pipe[5]
            comment = pipe[7]
            created_on = pipe[0]

            # ddl = 'CREATE PIPE ' + db + '.' + schema + '.' + name + ' as ' + pipe[4] + ';'
            sql = "select get_ddl('PIPE', '" + db + '.' + schema + '.' + name + "')"
            show_verbose(verbose, sql)
            ddl_tup = run_sql(conn, sql, False)
            ddl = ddl_tup[0]

            grants_list = get_grants_on_object(conn, 'PIPE', db + '.' + schema + '.' + name, verbose, objf, ignoreshare)

            info = {'NAME': name, 'CREATED': created_on, 'OWNER': role_owner, 'COMMENT': comment, 'SCHEMA': schema,
                    'DDL': ddl, 'GRANTS': grants_list}
            db_info['10-PIPES'] = info

            role_obj = database_objects[db]

            if role_owner in role_obj:
                role_obj[role_owner].append(db_info)
            else:
                role_obj[role_owner] = []
                role_obj[role_owner].append(db_info)

            database_objects[db] = role_obj

    return database_objects


def get_database_streams(conn, database_objects, verbose, just_schema, objf, ignoreshare):
    print('--Step 11.  Getting Streams List')
    # Loop through all the databases, or a single database and populate the stages.
    for db in database_objects.keys():
        if just_schema:
            sql = 'use database ' + db
            sqloutput = run_sql(conn, sql, False)
            sql = 'show streams in schema ' + just_schema
        else:
            sql = 'show streams in database ' + db
        show_verbose(verbose, sql)
        streams = run_sql(conn, sql, True)

        for stream in streams:
            db_info = {}
            role_obj = {}

            name = stream[1]
            schema = stream[3]
            role_owner = stream[4]
            comment = stream[5]
            created_on = stream[0]

            sql = "select get_ddl('STREAM', '" + db + '.' + schema + '.' + name + "')"
            show_verbose(verbose, sql)
            ddl_tup = run_sql(conn, sql, False)
            ddl = ddl_tup[0]

            grants_list = get_grants_on_object(conn, 'STREAM', db + '.' + schema + '.' + name, verbose, objf,
                                               ignoreshare)

            info = {'NAME': name, 'CREATED': created_on, 'OWNER': role_owner, 'COMMENT': comment, 'SCHEMA': schema,
                    'DDL': ddl, 'GRANTS': grants_list}
            db_info['11-STREAMS'] = info

            role_obj = database_objects[db]

            if role_owner in role_obj:
                role_obj[role_owner].append(db_info)
            else:
                role_obj[role_owner] = []
                role_obj[role_owner].append(db_info)

            database_objects[db] = role_obj

    return database_objects

def get_warehouse_list(conn, verbose, objf, ignoreshare):
    wh_list = {}

    print('--Step 12.   Getting Warehouse List')

    sql = 'show warehouses'

    show_verbose(verbose, sql)
    warehouses = run_sql(conn, sql, True)

    for warehouse in warehouses:
        name = warehouse[0]
        wh_type = warehouse[2]
        size = warehouse[3]
        min_cluster_count = warehouse[4]
        max_cluster_count = warehouse[5]
        auto_suspend = warehouse[11]
        auto_resume = warehouse[12]
        owner = warehouse[20]

        grants_list = get_grants_on_object(conn, 'WAREHOUSE', name, verbose, objf, ignoreshare)

        ddl = 'CREATE WAREHOUSE IF NOT EXISTS ' + name + " WITH WAREHOUSE_SIZE = '" + str(size) + "' SCALING_POLICY = '" + wh_type + "' AUTO_SUSPEND = " + str(auto_suspend) + " AUTO_RESUME = " + str(auto_resume)
        ddl = ddl + " MIN_CLUSTER_COUNT = " + str(min_cluster_count) + " MAX_CLUSTER_COUNT = " + str(max_cluster_count) + " INITIALLY_SUSPENDED = TRUE;"

        #info = {'DDL': ddl, 'GRANTS': grants_list}
        if owner not in wh_list:
            wh_list[owner] = []

        wh_list[owner].append(ddl)
        for grants in grants_list:
            wh_list[owner].append(grants)

    return wh_list

def print_ddl(database_objects, items, verbose, outputfile, roles, ddl_roles, warehouses_ddl, filemode):
    if outputfile:
        try:
            of = open(outputfile, filemode)
        except IOError:
            print("Could not open file! " + outputfile)
    else:
        of = ''

    # Using the w for write vs a for append flag to determine if we put the role information in the file.
    if roles and filemode == 'w':
        for role in ddl_roles.keys():
            printer('-------------------------------------', of)
            printer('-- Generating: Roles', of)
            printer('-------------------------------------', of)
            printer(role, of)
            for ddl in ddl_roles[role]['DDL']:
                printer(ddl, of)
            for grant in ddl_roles[role]['GRANTS']:
                printer(grant, of)
            for gu in ddl_roles[role]['GRANTS_USERS']:
                printer(gu, of)
            for priv in ddl_roles[role]['PRIVS']:
                printer(priv, of)
            printer('', of)


    printer('-------------------------------------', of)
    printer('-- Generating: Warehouses', of)
    printer('-------------------------------------', of)

    for role in warehouses_ddl.keys():
        printer('USE ROLE ' + role + ';', of)
        for ddl in warehouses_ddl[role]:
            printer(ddl, of)

    for db in sorted(database_objects.keys()):  # Database Name
        # Now loop through the new obj_hash to print out the ddl
        for item in sorted(items):
            printer('-------------------------------------', of)
            printer('-- Generating: ' + str(item), of)
            printer('-------------------------------------', of)
            if item != '01-DATABASE':
                printer('USE DATABASE ' + db + ';', of)
            role_obj = database_objects[db]
            for role in sorted(role_obj.keys()):  # Role Name
                first_time_flag = True
                obj_list = role_obj[role]  # Object list, 1-DATABASE, 2-SCHEMAS, etc.

                for obj in obj_list:
                    for key in sorted(obj.keys(), reverse=True):
                        if key == item:
                            schema = obj[key]['SCHEMA']
                            list = obj[key]['DDL']
                            list_grants = obj[key]['GRANTS']
                            if first_time_flag:
                                printer('USE ROLE ' + role + ';', of)
                                first_time_flag = False
                            if schema != '' and str(item) != '02-SCHEMAS':
                                printer('USE SCHEMA ' + schema + ';', of)
                            printer(list, of)
                            printer('', of)
                            for list_grant in list_grants:
                                # printer('--GRANTS', of)
                                printer(list_grant, of)
                            printer('', of)

    if of != '':
        if not of.closed:
            of.close()

    return


def printer(text, fh):
    if fh != '':
        if not fh.closed:
            fh.write(text + "\n")
    else:
        print(text)
    return


def extract_ddl(database_objects, item, verbose, outputfile, roles, ddl_roles):
    if outputfile:
        match = re.search('([\w.-]+)\.([\w.-]+)', outputfile)
        if match:
            outputfile = match.group(1) + '_extract.sql'
            outputfile2 = match.group(1) + '_load.sql'
        else:
            outputfile2 = outputfile + '_load.sql'
            outputfile = outputfile + '_extract.sql'

        try:
            of = open(outputfile, 'w')
        except IOError:
            print("Could not open file! " + outputfile)
        try:
            of2 = open(outputfile2, 'w')
        except IOError:
            print("Could not open file! " + outputfile2)
        print('')
        print('--Extract DDL file name -> ' + outputfile)
        print('--Load DDL file name -> ' + outputfile2)
    else:
        of = ''
        of2 = ''

    for db in sorted(database_objects.keys()):  # Database Name
        # Now loop through the new obj_hash to print out the ddl

        printer('-------------------------------------', of)
        printer('-- Generating Extract: ' + str(item), of)
        printer('-------------------------------------', of)
        printer('-------------------------------------', of2)
        printer('-- Generating LOAD: ' + str(item), of2)
        printer('-------------------------------------', of2)
        if item != '01-DATABASE':
            printer('USE DATABASE ' + db + ';', of)
            printer('USE DATABASE ' + db + ';', of2)
        role_obj = database_objects[db]
        for role in sorted(role_obj.keys()):  # Role Name
            first_time_flag = True
            obj_list = role_obj[role]  # Object list, 1-DATABASE, 2-SCHEMAS, etc.
            for obj in obj_list:
                for key in sorted(obj.keys(), reverse=True):
                    if key == item:
                        schema = obj[key]['SCHEMA']
                        # Check to see if the table is exportable, and if it is, if it contains a variant column use the Paquet format.
                        if obj[key]['EXPORTABLE'] == 'TRUE':
                            if obj[key]['VARIANT_FLAG'] == 'TRUE':
                                list = "copy into @UTIL_DB_MIGRATION.PUBLIC.EXTRACT_STAGE/" + db + "/" + schema + "/" + \
                                       obj[key]['NAME'] + '/' + obj[key]['NAME'] + ' from ' + db + "." + schema + "." + \
                                       obj[key][
                                           'NAME'] + " file_format=(format_name='UTIL_DB_MIGRATION.PUBLIC.PARQUET_FMT' compression='AUTO');"
                                list2 = "copy into " + db + "." + schema + "." + obj[key][
                                    'NAME'] + " from @UTIL_DB_MIGRATION.PUBLIC.EXTRACT_STAGE/" + db + "/" + schema + "/" + \
                                        obj[key]['NAME'] + '/' + obj[key][
                                            'NAME'] + " file_format=(format_name='UTIL_DB_MIGRATION.PUBLIC.PARQUET_FMT');"
                            else:
                                list = "copy into @UTIL_DB_MIGRATION.PUBLIC.EXTRACT_STAGE/" + db + "/" + schema + "/" + \
                                       obj[key]['NAME'] + '/' + obj[key]['NAME'] + ' from ' + db + "." + schema + "." + \
                                       obj[key][
                                           'NAME'] + " file_format=(format_name='UTIL_DB_MIGRATION.PUBLIC.CSV_FMT' compression='AUTO');"
                                list2 = "copy into " + db + "." + schema + "." + obj[key][
                                    'NAME'] + " from @UTIL_DB_MIGRATION.PUBLIC.EXTRACT_STAGE/" + db + "/" + schema + "/" + \
                                        obj[key]['NAME'] + '/' + obj[key][
                                            'NAME'] + " file_format=(format_name='UTIL_DB_MIGRATION.PUBLIC.CSV_FMT');"
                        else:
                            list = "-------- Object will have to be manually exported because it contains mixed columns or multiple varaiant columns: " + \
                                   obj[key]['NAME']
                            list2 = "-------- Object will have to be manually exported because it contains mixed columns or multiple varaiant columns: " + \
                                    obj[key]['NAME']
                        if first_time_flag:
                            printer('USE ROLE ' + role + ';', of)
                            printer('USE ROLE ' + role + ';', of2)
                            first_time_flag = False
                        if schema != '':
                            printer('USE SCHEMA ' + schema + ';', of)
                            printer('USE SCHEMA ' + schema + ';', of2)
                        printer(list, of)
                        printer('', of)
                        printer(list2, of2)
                        printer('', of2)

    if of2 != '':
        if not of2.closed:
            of2.close()
    if of != '':
        if not of.closed:
            of.close()

    return


def get_roles(conn, verbose):
    roles_all = {}
    ddl_roles = {}
    print('--Step 12.  Getting Roles List')
    if verbose:
        sql = "select current_version(), current_client(), current_account(), current_user(), current_role()"
        res = run_sql(conn, sql, False)
        print("Snowflake version: {0}, client: {1}, account: {2}, user: {3}, role: {4}".format(res[0], res[1], res[2],
                                                                                               res[3], res[4]))

    # get all roles
    sql = "show roles"
    roles = run_sql(conn, sql, True)
    print("--            Role count: " + str(len(roles)))

    for row in roles:
        if verbose:
            print("created: {0}, name: {1}, comment: {2}".format(row[0], row[1], row[9]))

        # remember each role and its comment
        role = row[1]
        owner = row[8]
        comment = row[9]

        # Add the use role to the DDL so the role is created with the same access.
        if len(owner) != 0:
            use_role = 'use role ' + owner + ';'
            ddl = 'CREATE ROLE IF NOT EXISTS ' + role + ';'
        else:
            use_role = 'use role ACCOUNTADMIN;'
            ddl = 'CREATE ROLE IF NOT EXISTS' + role + ';'

        # Comment out the DDL statement for the built in roles
        if role in ('ACCOUNTADMIN', 'SYSADMIN', 'SECURITYADMIN', 'PUBLIC', 'ORGADMIN', 'USERADMIN'):
            ddl = '--' + ddl

        # role_obj = {'name':role, 'comment':comment, 'OWNER':owner, 'USE_ROLE':use_role, 'DDL':ddl, 'GRANTS':[]}
        role_obj = {'name': role, 'comment': comment, 'OWNER': owner}
        roles_all[role] = role_obj

        # Build the DDL_ROLES dict to handle the looping through the roles for permissions.
        if use_role in ddl_roles:
            ddl_roles[use_role]['DDL'].append(ddl)
        else:
            ddl_roles[use_role] = {'DDL': [], 'GRANTS': [], 'GRANTS_USERS': [], 'PRIVS': []}
            ddl_roles[use_role]['DDL'].append(ddl)

    return (roles_all, ddl_roles)


def get_grants_to_role(conn, verbose, roles_all, ddl_roles, objf):
    print('--Step 13.  Getting Grants on Role List')
    for role in roles_all.keys():

        sql = 'show grants to role "{0}"'.format(role)
        # sql = 'show grants on role "{0}"'.format(role)
        if verbose:
            print(sql)

        privs = run_sql(conn, sql, True)
        for row in privs:
            privilege = row[1]
            granted_on = row[2]
            object_name = row[3]
            granted_to = row[4]
            grantee = row[5]
            grant_option = row[6]
            granted_by = row[7]

            if len(granted_by) == 0:
                granted_by = 'ACCOUNTADMIN'

            use_role = 'use role ' + granted_by + ';'

            if granted_on == 'ACCOUNT':
                object_name = ''

            if grant_option == 'true':
                grant = 'grant ' + privilege + ' on ' + granted_on + ' ' + object_name + ' to ' + granted_to + ' ' + grantee + ' with grant option;'
                printer(grantee + '|' + granted_to + '|' + privilege + '|' + granted_on + '|' + object_name, objf)
            else:
                grant = grant = 'grant ' + privilege + ' on ' + granted_on + ' ' + object_name + ' to ' + granted_to + ' ' + grantee + ';'
                printer(grantee + '|' + granted_to + '|' + privilege + '|' + granted_on + '|' + object_name, objf)

            # Build the DDL_ROLES dict to handle the looping through the roles for permissions.
            # if privilege not in ('USAGE', 'OWNERSHIP'):
            # if privilege in ('WAREHOUSE', 'ACCOUNT'):
            # 2020-06-04 fix applied.
            if granted_on in ('WAREHOUSE', 'ACCOUNT'):
                if use_role in ddl_roles:
                    ddl_roles[use_role]['PRIVS'].append(grant)
                else:
                    ddl_roles[use_role] = {'DDL': [], 'GRANTS': [], 'GRANTS_USERS': [], 'PRIVS': []}
                    ddl_roles[use_role]['PRIVS'].append(grant)

    return (roles_all, ddl_roles)


def get_grants_of_role(conn, verbose, roles_all, ddl_roles, off):
    print('--Step 14.  Getting Grants of Role List')
    print('')
    print('--Role Hierarchy')
    print('-------------------------------------------------------')
    roles_tree = {}
    for role in roles_all.keys():

        sql = 'show grants of role "{0}"'.format(role)
        if verbose:
            print(sql)

        grants = run_sql(conn, sql, True)

        parent_count = 0
        for row in grants:
            if verbose:
                print("created: {0}, role: {1}, granted_to: {2}, grantee: {3}, granted by: {4}".format(row[0], row[1],
                                                                                                       row[2], row[3],
                                                                                                       row[4]))

            # role = row[1]   #already populated based on the role key.
            granted_to = row[2]
            grantee = row[3]
            granted_by = row[4]

            if granted_by == '':
                granted_by = 'ACCOUNTADMIN'

            if granted_to == 'ROLE':
                parent_count += 1
                if verbose:
                    print("\trole {0} parent: {1}".format(role, grantee))

                parent = roles_all[grantee]  # Ex.  AccountAdmin parent
                child = roles_all[role]  # Ex.  Sysadmin  child

                children = parent.get('children')  # check to see if children is in the list.
                if children != None:
                    children.append(child)  # Ex. Adds new item to the list children.
                else:
                    children = [child]  # Ex. Defines a list of children and adds sysadmin
                    parent['children'] = children  # Ex. dict parent['children']= list of children

                # Build the DDL_ROLES dict to handle the looping through the roles for permissions.
                use_role = 'use role ' + granted_by + ';'
                if not (role in ('ACCOUNTADMIN', 'SYSADMIN', 'SECURITYADMIN', 'ORGADMIN', 'PUBLIC', 'USERADMIN')
                        and grantee in ('ACCOUNTADMIN', 'SYSADMIN', 'SECURITYADMIN', 'ORGADMIN', 'PUBLIC', 'USERADMIN')):
                    grant = 'grant role ' + role + ' to role ' + grantee + ';'
                    printer(role + '|' + grantee + '|' + 'ROLE', off)

                if use_role in ddl_roles:
                    ddl_roles[use_role]['GRANTS'].append(grant)
                else:
                    ddl_roles[use_role] = {'DDL': [], 'GRANTS': [], 'GRANTS_USERS': [], 'PRIVS': []}
                    ddl_roles[use_role]['GRANTS'].append(grant)

                if verbose:
                    print("\t", role, children)

            if granted_to == 'USER':
                if verbose:
                    print("\trole {0} granted to: {1}".format(role, grantee))

                parent = roles_all[role]
                users = parent.get('users')
                if users != None:
                    users.append(grantee)
                else:
                    users = [grantee]
                    parent['users'] = users  # Ex. dict parent['users']= list of users

                # Build the DDL_ROLES dict to handle the looping through the roles for permissions.
                use_role = 'use role ' + granted_by + ';'
                grant = 'grant role ' + role + ' to user "' + grantee + '";'
                printer(grantee + '|' + role + '|' + 'USER', off)

                if use_role in ddl_roles:
                    ddl_roles[use_role]['GRANTS_USERS'].append(grant)
                else:
                    ddl_roles[use_role] = {'DDL': [], 'GRANTS': [], 'GRANTS_USERS': [], 'PRIVS': []}
                    ddl_roles[use_role]['GRANTS_USERS'].append(grant)

                if verbose:
                    print("\t", grantee, users)

            if parent_count == 0:
                # this role has no parents, add to root of tree
                if verbose:
                    print("role '" + role + "' has no parents")
                roles_tree[role] = roles_all[role]

        # Add the public role to the roles_tree hierarchy in case it has no direct privs.
        if 'PUBLIC' not in roles_tree.keys():
            roles_tree['PUBLIC'] = roles_all['PUBLIC']

    return (roles_all, roles_tree, ddl_roles)


def print_roles(all_roles, roles_tree, level, showusers, comments, db_obj, off):
    for key in sorted(roles_tree.keys()):
        role_obj = all_roles[key]
        print_role(role_obj, level, showusers, comments, db_obj, off)

    return


def print_role(role_obj, level, showusers, comments, db_obj, off):
    indent = '  ' * level
    name = role_obj['name']
    role = role_obj['name']

    # added below two lines to build out the grants_of_role.csv file.
    if level == 0:
        printer(role + '|' + '|' + 'ROLE', off)

    # mark system roles with square brackets so they stand out
    if name in ('ACCOUNTADMIN', 'SYSADMIN', 'SECURITYADMIN', 'PUBLIC'):
        name = "[" + name + "]"

    str = indent + name
    comm = role_obj['comment']
    if comments and len(comm) > 0:
        str += "\t(" + comm + ")"
    print(str)

    # ---------------------------------------------------
    #  Print out the Database objects for this role
    # ---------------------------------------------------
    for db in db_obj.keys():
        if role in db_obj[db]:
            for itemtype in db_obj[db][role]:  # 1-Database, 2-SCHEMAS, 3-TABLES
                for k, v in itemtype.items():
                    if k in ('01-DATABASE', '02-SCHEMAS'):
                        print(indent + '  Granted Access to: ' + k + ' \t\tObject: ' + v['NAME'])
                    else:
                        print(indent + '  Granted Access to: ' + k + ' \t\tObject: ' + db + '.' + v['SCHEMA'] + '.' + v[
                            'NAME'])
                    # Now loop through any individual object grants
                    for grant in v['GRANTS']:
                        print(indent + '  Granted Individual Access to: ' + k + ' \t\tObject: ' + grant)

    # print users that have been granted this role
    if showusers:
        str = indent + "  " + "granted to user: "
        users = role_obj.get('users')
        if users != None:
            for obj in users:
                print(str + obj)

    # recurse into our "children" (roles granted to the current "parent" role)
    children = role_obj.get('children')
    if children != None:
        n = level + 1
        for obj in children:
            print_role(obj, n, showusers, comments, db_obj, off)

    return

