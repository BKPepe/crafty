import logging
import tornado.web
import tornado.escape

from app.classes.console import console
from app.classes.models import *
from app.classes.handlers.base_handler import BaseHandler
from app.classes.multiserv import multi

logger = logging.getLogger(__name__)

class PublicHandler(BaseHandler):

    def initialize(self):
        self.console = console

    def set_current_user(self, user):
        if user:
            self.set_secure_cookie("user", tornado.escape.json_encode(user), expires_days=1)
        else:
            self.clear_cookie("user")

    def get(self, page=None):

        self.clear_cookie("user")
        template = "public/login.html"
        context = {'login': None}

        server_data = multi.get_stats_for_servers()
        server_list = []

        for key, value in server_data.items():
            server_list.append(value)

        context['server_data'] = server_list

        self.render(
            template,
            data=context
        )


    def post(self):
        entered_user = self.get_argument('username')
        entered_password = self.get_argument('password')


        try:
            user_data = Users.get(Users.username == entered_user)

            if user_data:
                # if the login is good and the pass verified, we go to the dashboard
                login_result = helper.verify_pass(entered_password, user_data.password)
                if login_result:
                    self.set_current_user(entered_user)

                    if helper.check_file_exists(helper.new_install_file):
                        next_page = "/setup/step1"
                    else:
                        next_page = '/admin/dashboard'

                    self.redirect(next_page)
        except:
            pass


        template = "public/login.html"
        context = {'login': None}

        server_data = multi.get_stats_for_servers()
        server_list = []

        for key, value in server_data.items():
            server_list.append(value)

        context['server_data'] = server_list

        self.render(
            template,
            data=context
        )