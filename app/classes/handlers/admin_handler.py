import time
import logging
import schedule
import threading
import tornado.web
import tornado.escape
from pathlib import Path

from app.classes.console import console
from app.classes.models import *
from app.classes.handlers.base_handler import BaseHandler
from app.classes.web_sessions import web_session
from app.classes.multiserv import multi
from app.classes.ftp import ftp_svr_object
from app.classes.backupmgr import backupmgr

logger = logging.getLogger(__name__)

class AdminHandler(BaseHandler):

    def initialize(self, mcserver):
        self.mcserver = mcserver
        self.console = console
        self.session = web_session(self.current_user)

    @tornado.web.authenticated
    def get(self, page):

        name = tornado.escape.json_decode(self.current_user)
        user_data = get_perms_for_user(name)

        context = {
            'user_data': user_data,
            'version_data': helper.get_version(),
            'servers_defined': multi.list_servers(),
            'managed_server': self.session.get_data(self.current_user, 'managed_server'),
            'servers_running': multi.list_running_servers(),
            'mc_servers_data': multi.get_stats_for_servers()
        }

        if page == 'unauthorized':
            template = "admin/denied.html"

        elif page == "reload_web":
            template = "admin/reload_web_settings.html"

            web_data = Webserver.get()
            page_data = {}
            page_data['user_data'] = user_data
            page_data['web_settings'] = model_to_dict(web_data)
            context = page_data

            self.render(
                template,
                data=context
            )
            # reload web server
            Remote.insert({
                Remote.command: 'restart_web_server',
                Remote.server_id: 1,  # this doesn't really matter as we are not tying to a server
                Remote.command_source: 'local'
            }).execute()

        elif page == 'reload_mc_settings':
            Remote.insert({
                Remote.command: 'reload_mc_settings',
                Remote.server_id: 1, # this doesn't really matter as we are not tying to a server
                Remote.command_source: 'local'

            }).execute()

            self.redirect("/admin/config")

        elif page == 'dashboard':
            errors = self.get_argument('errors', None)
            context['errors'] = errors
            context['host_stats'] = multi.get_host_status()

            template = "admin/dashboard.html"

        elif page == 'change_password':
            template = "admin/change_pass.html"

        elif page == 'virtual_console':
            if not check_role_permission(user_data['username'], 'svr_console'):
                self.redirect('/admin/unauthorized')

            context['server_id'] = self.get_argument('id', '')

            mc_data = MC_settings.get_by_id(context['server_id'])

            context['server_name'] = mc_data.server_name

            template = "admin/virt_console.html"

        elif page == "backups":
            if not check_role_permission(user_data['username'], 'backups'):
                self.redirect('/admin/unauthorized')
                
            server_id = self.get_argument('id', '')
            mc_data = MC_settings.get_by_id(server_id)
            
            template = "admin/backups.html"

            backup_data = Backups.get_by_id(server_id)

            backup_data = model_to_dict(backup_data)

            backup_path = backup_data['storage_location']
            backup_dirs = json.loads(backup_data['directories'])

            context['backup_data'] = json.loads(backup_data['directories'])
            context['backup_config'] = backup_data

            # get a listing of directories in the server path.
            context['directories'] = helper.scan_dirs_in_path(mc_data.server_path)

            context['server_root'] = mc_data.server_path

            context['server_name'] = mc_data.server_name
            context['server_id'] = mc_data.id
            context['backup_paths'] = backup_dirs
            context['backup_path'] = backup_path
            context['current_backups'] = backupmgr.list_backups_for_server(server_id)

            context['saved'] = False
            context['invalid'] = False

        elif page == "all_backups":
            if not check_role_permission(user_data['username'], 'backups'):
                self.redirect('/admin/unauthorized')

            template = "admin/backups.html"
            # END
            
            backup_list = Backups.get()
            backup_data = model_to_dict(backup_list)
            backup_path = backup_data['storage_location']
            backup_dirs = json.loads(backup_data['directories'])
            
            context['backup_paths'] = backup_dirs
            context['backup_path'] = backup_path
            context['current_backups'] = backupmgr.list_all_backups()
            context['server_name'] = "All Servers"

        elif page == "schedules":
            if not check_role_permission(user_data['username'], 'schedules'):
                self.redirect('/admin/unauthorized')

            saved = self.get_argument('saved', None)

            db_data = Schedules.select()

            template = "admin/schedules.html"
            context['db_data'] = db_data
            context['saved'] = saved

        elif page == "reloadschedules":
            if not check_role_permission(user_data['username'], 'schedules'):
                self.redirect('/admin/unauthorized')

            logger.info("Reloading Scheduled Tasks")

            db_data = Schedules.select()

            # clear all user jobs
            schedule.clear('user')

            logger.info("Deleting all old tasks")

            logger.info("There are {} scheduled jobs to parse:".format(len(db_data)))

            # loop through the tasks in the db
            for task in db_data:
                helper.scheduler(task, self.mcserver)

            template = "admin/schedules.html"
            context['db_data'] = db_data
            context['saved'] = None

        elif page == "schedule_disable":
            if not check_role_permission(user_data['username'], 'schedules'):
                self.redirect('/admin/unauthorized')

            schedule_id = self.get_argument('id', None)
            q = Schedules.update(enabled=0).where(Schedules.id == schedule_id)
            q.execute()

            self.redirect("/admin/reloadschedules")

        elif page == "schedule_enable":
            if not check_role_permission(user_data['username'], 'schedules'):
                self.redirect('/admin/unauthorized')

            schedule_id = self.get_argument('id', None)
            q = Schedules.update(enabled=1).where(Schedules.id == schedule_id)
            q.execute()

            self.redirect("/admin/reloadschedules")

        elif page == 'config':
            if not check_role_permission(user_data['username'], 'config'):
                self.redirect('/admin/unauthorized')

            saved = self.get_argument('saved', None)
            invalid = self.get_argument('invalid', None)

            template = "admin/config.html"
            crafty_data = Crafty_settings.get()

            web_data = Webserver.get()
            users = Users.select()

            page_data = {}
            context['saved'] = saved
            context['invalid'] = invalid

            context['crafty_settings'] = model_to_dict(crafty_data)
            context['web_settings'] = model_to_dict(web_data)

            context['users'] = users
            context['users_count'] = len(users)

        elif page == 'server_config':
            if not check_role_permission(user_data['username'], 'config'):
                self.redirect('/admin/unauthorized')

            saved = self.get_argument('saved', None)
            invalid = self.get_argument('invalid', None)
            server_id = self.get_argument('id', None)
            errors = self.get_argument('errors', None)

            context['errors'] = errors

            if server_id is None:
                self.redirect("/admin/dashboard")

            template = "admin/server_config.html"

            mc_data = MC_settings.get_by_id(server_id)

            page_data = {}
            context['saved'] = saved
            context['invalid'] = invalid
            context['mc_settings'] = model_to_dict(mc_data)

            context['server_root'] = context['mc_settings']['server_path']

            srv_obj = multi.get_server_obj(server_id)
            context['server_running'] = srv_obj.check_running()

            host_data = Host_Stats.get()
            context['max_memory'] = host_data.mem_total

        elif page == 'downloadbackup':
            if not check_role_permission(user_data['username'], 'backups'):
                self.redirect('/admin/unauthorized')

            path = self.get_argument("file", None, True)
            server_id = self.get_argument("id", None, True)

            # let's make sure this path is in the backup directory and not somewhere else
            # we don't want someone passing a path like /etc/passwd in the raw, so we are only passing the filename
            # to this function, and then tacking on the storage location in front of the filename.

            backup_folder = backupmgr.get_backup_folder_for_server(server_id)

            # Grab our backup path from the DB
            backup_list = Backups.get(Backups.server_id == int(server_id))
            server_backup_file = os.path.join(backup_list.storage_location, backup_folder, path)

            if server_backup_file is not None and helper.check_file_exists(server_backup_file):
                file_name = os.path.basename(server_backup_file)
                self.set_header('Content-Type', 'application/octet-stream')
                self.set_header('Content-Disposition', 'attachment; filename=' + file_name)

                with open(server_backup_file, 'rb') as f:
                    while 1:
                        data = f.read(16384)  # or some other nice-sized chunk
                        if not data:
                            break
                        self.write(data)
                self.finish()

            self.redirect("/admin/backups?id={}".format(server_id))

        elif page == "server_control":
            if not check_role_permission(user_data['username'], 'svr_control'):
                self.redirect('/admin/unauthorized')

            server_id = self.get_argument('id', None)

            if server_id is None:
                self.redirect("/admin/dashboard")

            template = "admin/server_control.html"
            logfile = helper.get_crafty_log_file()

            mc_data = MC_settings.get()

            srv_obj = multi.get_server_obj(server_id)
            context['server_running'] = srv_obj.check_running()
            context['mc_settings'] = model_to_dict(mc_data)
            context['server_updating'] = self.mcserver.check_updating()
            context['players'] = context['mc_servers_data'][int(server_id)]['players'].split(',')
            context['players_online'] = context['mc_servers_data'][int(server_id)]['online_players']

        elif page == 'commands':
            if not check_role_permission(user_data['username'], 'svr_console'):
                self.redirect('/admin/unauthorized')

            command = self.get_argument("command", None, True)
            id = self.get_argument("id", None, True)

            # grab any defined server object and reload the settings
            any_serv_obj = multi.get_first_server_object()
            any_serv_obj.reload_settings()

            if command == "server_stop":
                Remote.insert({
                    Remote.command: 'stop_mc_server',
                    Remote.server_id: id,
                    Remote.command_source: "localhost"
                }).execute()
                next_page = "/admin/virtual_console?id={}".format(id)

            elif command == "server_start":
                Remote.insert({
                    Remote.command: 'start_mc_server',
                    Remote.server_id: id,
                    Remote.command_source: "localhost"
                }).execute()
                next_page = "/admin/virtual_console?id={}".format(id)

            elif command == "server_restart":
                Remote.insert({
                    Remote.command: 'restart_mc_server',
                    Remote.server_id: id,
                    Remote.command_source: "localhost"
                }).execute()
                next_page = "/admin/virtual_console?id={}".format(id)

            elif command == "ftp_server_start":
                Remote.insert({
                    Remote.command: 'start_ftp',
                    Remote.server_id: id,
                    Remote.command_source: 'localhost'
                }).execute()
                time.sleep(2)
                next_page = "/admin/files?id={}".format(id)

            elif command == 'ftp_server_stop':
                Remote.insert({
                    Remote.command: 'stop_ftp',
                    Remote.server_id: id,
                    Remote.command_source: 'localhost'
                }).execute()
                time.sleep(2)
                next_page = "/admin/files?id={}".format(id)

            elif command == "backup":
                backupmgr.backup_server(id)
                time.sleep(4)
                next_page = '/admin/backups?id={}'.format(id)
            
            elif command == "backup_all":
                backupmgr.backup_all_servers()
                time.sleep(4)
                next_page = '/admin/backups'

            self.redirect(next_page)

        elif page == 'get_logs':
            if not check_role_permission(user_data['username'], 'logs'):
                self.redirect('/admin/unauthorized')

            server_id = self.get_argument('id', None)
            mc_data = MC_settings.get_by_id(server_id)

            context['server_name'] = mc_data.server_name
            context['server_id'] = server_id

            srv_object = multi.get_server_obj(server_id)

            data = []

            server_log = os.path.join(mc_data.server_path, 'logs', 'latest.log')

            if server_log is not None:
                data = helper.tail_file(server_log, 500)
                data.insert(0, "Lines trimmed to ~500 lines for speed sake \n ")
            else:
                data.insert(0, "Unable to find {} \n ".format(
                    os.path.join(mc_data.server_path, 'logs', 'latest.log')))

            crafty_data = helper.tail_file(helper.crafty_log_file, 100)
            crafty_data.insert(0, "Lines trimmed to ~100 lines for speed sake \n ")

            scheduler_data = helper.tail_file(os.path.join(helper.logs_dir, 'schedule.log'), 100)
            scheduler_data.insert(0, "Lines trimmed to ~100 lines for speed sake \n ")

            access_data = helper.tail_file(os.path.join(helper.logs_dir, 'tornado-access.log'), 100)
            access_data.insert(0, "Lines trimmed to ~100 lines for speed sake \n ")

            ftp_data = helper.tail_file(os.path.join(helper.logs_dir, 'ftp.log'), 100)
            ftp_data.insert(0, "Lines trimmed to ~100 lines for speed sake \n ")

            errors = srv_object.search_for_errors()
            template = "admin/logs.html"

            context['log_data'] = data
            context['errors'] = errors
            context['crafty_log'] = crafty_data
            context['scheduler'] = scheduler_data
            context['access'] = access_data
            context['ftp'] = ftp_data

        elif page == "files":
            if not check_role_permission(user_data['username'], 'files'):
                self.redirect('/admin/unauthorized')

            template = "admin/files.html"

            server_id = self.get_argument('id', None)
            context['server_id'] = server_id

            srv_object = multi.get_server_obj(server_id)
            context['pwd'] = srv_object.server_path

            context['listing'] = helper.scan_dirs_in_path(context['pwd'])
            context['parent'] = None

            context['ext_list'] = [".txt", ".yml", "ties", "json", '.conf']

            ftp_data = Ftp_Srv.get()
            context['ftp_settings'] = model_to_dict(ftp_data)
            context['ftp_running'] = ftp_svr_object.check_running()
            context['ftp_root'] = ftp_svr_object.get_root_dir()

        else:
            # 404
            template = "public/404.html"
            context = {}

        self.render(
            template,
            data=context
        )

    @tornado.web.authenticated
    def post(self, page):

        name = tornado.escape.json_decode(self.current_user)
        user_data = get_perms_for_user(name)

        #server_data = self.get_server_data()
        context = {
            'user_data': user_data,
            'version_data': helper.get_version(),
            'servers_defined': multi.list_servers(),
            'managed_server': self.session.get_data(self.current_user, 'managed_server'),
            'servers_running': multi.list_running_servers(),
            'mc_servers_data': multi.get_stats_for_servers()
        }

        if page == 'change_password':
            entered_password = self.get_argument('password')
            encoded_pass = helper.encode_pass(entered_password)

            q = Users.update({Users.password: encoded_pass}).where(Users.username == user_data['username'])
            q.execute()

            self.clear_cookie("user")
            self.redirect("/")

        elif page == 'schedules':
            action = self.get_argument('action', '')
            interval = self.get_argument('interval', '')
            interval_type = self.get_argument('type', '')
            sched_time = self.get_argument('time', '')
            command = self.get_argument('command', '')
            comment = self.get_argument('comment', '')

            result = (
                Schedules.insert(
                    enabled=True,
                    action=action,
                    interval=interval,
                    interval_type=interval_type,
                    start_time=sched_time,
                    command=command,
                    comment=comment
                )
                    .on_conflict('replace')
                    .execute()
            )
            self.redirect("/admin/schedules?saved=True")

        elif page == 'config':

            config_type = self.get_argument('config_type')

            if config_type == 'mc_settings':

                # Define as variables to eliminate multiple function calls, slowing the processing down
                server_path = self.get_argument('server_path')
                server_jar = self.get_argument('server_jar')

                server_path_exists = helper.check_directory_exist(server_path)

                # Use pathlib to join specified server path and server JAR file then check if it exists
                jar_exists = helper.check_file_exists(os.path.join(server_path, server_jar))

                if server_path_exists and jar_exists:
                    q = MC_settings.update({
                        MC_settings.server_name: self.get_argument('server_name'),
                        MC_settings.server_path: server_path,
                        MC_settings.server_jar: server_jar,
                        MC_settings.memory_max: self.get_argument('memory_max'),
                        MC_settings.memory_min: self.get_argument('memory_min'),
                        MC_settings.additional_args: self.get_argument('additional_args'),
                        MC_settings.pre_args: self.get_argument('pre_args'),
                        MC_settings.auto_start_server: int(self.get_argument('auto_start_server')),
                        MC_settings.server_port: self.get_argument('server_port'),
                        MC_settings.server_ip: self.get_argument('server_ip'),
                        MC_settings.jar_url: self.get_argument('jar_url'),
                        MC_settings.crash_detection: self.get_argument('crash_detection')
                    }).where(MC_settings.id == 1)

                    q.execute()
                    self.mcserver.reload_settings()

                elif server_path_exists:
                    # Redirect to "config invalid" page and log an event
                    logger.error('Minecraft server JAR does not exist at {}'.format(server_path))
                    self.redirect("/admin/config?invalid=True")

                else:
                    logger.error('Minecraft server directory or JAR does not exist')
                    self.redirect("/admin/config?invalid=True")

            self.redirect("/admin/config?saved=True")

        elif page == "server_config":
            # Define as variables to eliminate multiple function calls, slowing the processing down
            server_path = self.get_argument('server_path')
            server_jar = self.get_argument('server_jar')
            server_id = self.get_argument('server_id')
            server_name = self.get_argument('server_name')
            errors = self.get_argument('errors', None)

            context['errors'] = errors

            server_path_exists = helper.check_directory_exist(server_path)

            # Use pathlib to join specified server path and server JAR file then check if it exists
            jar_exists = helper.check_file_exists(os.path.join(server_path, server_jar))

            if server_path_exists and jar_exists:
                MC_settings.update({
                    MC_settings.server_name: server_name,
                    MC_settings.server_path: server_path,
                    MC_settings.server_jar: server_jar,
                    MC_settings.memory_max: self.get_argument('memory_max'),
                    MC_settings.memory_min: self.get_argument('memory_min'),
                    MC_settings.additional_args: self.get_argument('additional_args'),
                    MC_settings.pre_args: self.get_argument('pre_args'),
                    MC_settings.auto_start_server: int(self.get_argument('auto_start_server')),
                    MC_settings.auto_start_delay: int(self.get_argument('auto_start_delay')),
                    MC_settings.auto_start_priority: int(self.get_argument('auto_start_priority')),
                    MC_settings.crash_detection: self.get_argument('crash_detection'),
                    MC_settings.server_port: self.get_argument('server_port'),
                    MC_settings.server_ip: self.get_argument('server_ip'),
                    MC_settings.jar_url: self.get_argument('jar_url'),
                }).where(MC_settings.id == server_id).execute()

                srv_obj = multi.get_first_server_object()
                srv_obj.reload_settings()

                self.redirect("/admin/dashboard")

            elif server_path_exists:
                # Redirect to "config invalid" page and log an event
                logger.error('Minecraft server JAR does not exist at {}'.format(server_path))
                self.redirect("/admin/server_config?id={}&errors={}".format(server_id, "Server Jar Does Not Exists"))

            else:
                logger.error('Minecraft server directory or JAR does not exist')
                self.redirect("/admin/server_config?id={}&errors={}".format(server_id, "Server Path Does Not Exists"))

        elif page == 'files':

            next_dir = self.get_argument('next_dir')
            path = Path(next_dir)

            template = "admin/files.html"
            context['pwd'] = next_dir

            context['listing'] = helper.scan_dirs_in_path(context['pwd'])

            mc_data = MC_settings.get()
            mc_settings = model_to_dict(mc_data)

            ftp_data = Ftp_Srv.get()
            context['ftp_settings'] = model_to_dict(ftp_data)

            mc_settings['server_path'] = str(mc_settings['server_path']).replace("\\", '/')
            if next_dir == mc_settings['server_path']:
                context['parent'] = None
            else:
                context['parent'] = path.parent
                context['parent'] = str(context['parent']).replace("\\", '/')

            context['ext_list'] = [".txt", ".yml", "ties", "json", '.conf']
            context['ftp_running'] = ftp_svr_object.check_running()

            self.render(
                template,
                data=context
            )

        elif page == 'add_server':
            server_name = self.get_argument('server_name', '')
            server_path = self.get_argument('server_path', '')
            server_jar = self.get_argument('server_jar', '')
            max_mem = self.get_argument('max_mem', '')
            min_mem = self.get_argument('min_mem', '')
            auto_start = self.get_argument('auto_start', '')

            samename = MC_settings.select().where(MC_settings.server_name == server_name)
            if samename.exists():
                logger.error("2 servers can't have the same name - Can't add server")
                error = "Another server is already called: {}".format(server_name)


            error = None

            # does this server path / jar exist?
            server_path_exists = helper.check_directory_exist(server_path)

            if not server_path_exists:
                logger.error("Server path {} doesn't exist - Can't add server".format(server_path))
                error = "Server Path Does Not Exists"

            # Use pathlib to join specified server path and server JAR file then check if it exists
            jar_exists = helper.check_file_exists(os.path.join(server_path, server_jar))

            if not jar_exists and error is None:
                logger.error("Server jar {} doesn't exist - Can't add server".format(
                    os.path.join(server_path, server_jar))
                )
                error = "Server Jar Does Not Exists"

            # does a server with this name already exists?
            existing = MC_settings.select(MC_settings.server_name).where(MC_settings.server_name == server_name)
            if existing and error is None:
                logger.error("A server with that name already exists - Can't add server {}".format(server_name))
                error = "A server with that name already exists"

            if error is None:
                new_server_id = MC_settings.insert({
                    MC_settings.server_name: server_name,
                    MC_settings.server_path: server_path,
                    MC_settings.server_jar: server_jar,
                    MC_settings.memory_max: max_mem,
                    MC_settings.memory_min: min_mem,
                    MC_settings.additional_args: "",
                    MC_settings.auto_start_server: auto_start,
                    MC_settings.auto_start_delay: 10,
                    MC_settings.auto_start_priority: 1,
                    MC_settings.crash_detection: 0,
                    MC_settings.server_port: 25565,
                    MC_settings.server_ip: "127.0.0.1"
                }).execute()

                logger.info("Added ServerID: {} - {}".format(new_server_id, server_name))

                multi.setup_new_server_obj(new_server_id)
                multi.do_stats_for_servers()
                self.redirect("/admin/dashboard")
            else:
                self.redirect("/admin/dashboard?errors={}".format(error))

        elif page == 'backups':
            checked = self.get_arguments('backup', False)
            max_backups = self.get_argument('max_backups', None)
            backup_storage = self.get_argument('storage_location', None)
            server_id = self.get_argument('server_id', None)

            if len(checked) == 0 or len(max_backups) == 0 or len(backup_storage) == 0:
                logger.error('Backup settings Invalid: Checked: {}, max_backups: {}, backup_storage: {}'
                             .format(checked, max_backups, backup_storage))
                self.redirect("/admin/config?invalid=True")

            else:
                logger.info("Backup directories set to: {}".format(checked))
                json_dirs = json.dumps(list(checked))

                Backups.update(
                    {
                        Backups.directories: json_dirs,
                        Backups.max_backups: max_backups,
                        Backups.storage_location: backup_storage,
                        Backups.server_id: int(server_id)
                    }
                ).where(Backups.server_id == int(server_id)).execute()

            self.redirect("/admin/backups?id={}".format(server_id))

