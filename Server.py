"""
author: Idan Pogrebinsky

-- Server Client --
"""



from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import socket
import threading
from sqlite3 import *

from tkinter import *
from tkinter import ttk
from ttkthemes import ThemedStyle
from time import sleep
from hashlib import md5
from copy import deepcopy
import PIL
from PIL import ImageTk
import random
import time
# TODO: improve the handshake mechanism, let the server update the bus regarding some important constants
# TODO: add RSA encryption over the handshake
# TODO: add a layer of symmetrical encryption over the rest of the
#       communication using a key that will be hand out during the handshake
# TODO: consider adding a remote server access
# TODO: when a bus connects to the server, update him regarding how many stations there are
# TODO: when the heartbeat mechanism starts, it should update the bus regarding how long each pulse is
# TODO: mark unactive lines that were requested
# TODO: support both directions for a line
# TODO: notify the users when a bus leaves the system
# TODO: don't let buses join with wrong station numbers
# TODO: make an anti fat finger for the all buttons
# TODO: make it run as an exe file
# TODO: upon server shutdown, use the datasender self.__shutdown to send all the buses that the server shut down
# TODO:upgrade the loading screen so it will be a bit smarter


class TelegramController:
    """
    The telegram controller class takes care of the telegram bot and all the communication with the end users.
    Receives commands from the telegram chat and can communicate with the bus controller

    possible commands that the server knows how to handle:
    /start - sends a greeting message
    /help - shows the help menu
    /request - place a request for a bus
    /cancel - cancel a request for a bus
    /show - takes another parameter, can show lines, buses,and the user requests
    /whatsmyid - tells the user his id, (it's a hidden command that is used to promote an admin)
    /checkadmin - tells the users wherever he is an admin or not (it's a hiddan command)
        - admin commands -
    /promote - can promote users to an admin rank
    /demote - can demote users from admin rank
    /kick - lets admins kick all the buses or all the users from the system
    /stop - stops the server
    """

    def __init__(self, token: str):
        """
        loads the needed information for the bot, gets access to the bus_controller and loads the list of bus stations
        :return: TelegramController
        """

        self.__token = token
        self.__message_sender = None
        self.bus_controller = None
        self.__updater = None
        self.__dp = None
        self.__users = dict()  # dictonary {id: user} (str: User)
        self.__gui = None

    def connect(self, bus_controller, gui, message_sender, data_base):
        """
        Used to get the needed connections with the outer work units.
        Must be ran before using the self.start() command.

        :param bus_controller: BusController - works with the buses
        :param gui: GUI - makes sure  that the information will be displayed
        :param message_sender: MessageSender - sends messages to buses
        :param data_base: DBManager -  takes  care of all the db related functions
        :return: None
        """

        self.bus_controller = bus_controller
        self.__gui = gui
        self.__message_sender = message_sender
        self.data_base = data_base

    def start(self):
        """
        makes sure that the instance has all the required connections to run
        if everything is valid a thread that holds all the handlers will be launched
        :return: None
        """

        if self.bus_controller == None:
            print("connection to the bus controller not established yet")
            return
        if self.__gui == None:
            print("connection to the GUI not established yet")
            return
        if self.__message_sender == None:
            print("Connection to the message sender not established yet")
            return

        update_tracking_thread = threading.Thread(target=self.__luanch_handlers, args=(),
                                                  name="Telegram Controller thread")
        update_tracking_thread.start()

    def stop(self):
        """
        Tells all users that the server shuts down
        Stops the handlers
        :return: None
        """

        for user in self.__users.values():
            text = f"Hello {user.name.split(' ')[0]}\n" \
                   f"The server is shutting down, your request will be removed\n" \
                   f"Bus4U service wishes you the best"

            self.data_base.log(user, "None", text)
            user.send_message(text)
        self.__updater.stop()

    @property
    def people_count(self):
        """
        counts how many people have placed a request in the system
        uses the telegram id to avoid counting the same person tice
        :return: int
        """
        return len(self.__users)

    def __luanch_handlers(self):
        """
        takes up a thread of it's own as it's endless.
        manage all the inputs that come from the telegram users through the bot
        :return: None
        """

        self.__updater = Updater(self.__token, use_context=True)
        self.__dp = self.__updater.dispatcher
        # on different commands - answer in Telegram
        self.__dp.add_handler(CommandHandler("start", self.start_message))
        self.__dp.add_handler(CommandHandler("help", self.help))
        self.__dp.add_handler(CommandHandler("history", self.history))
        self.__dp.add_handler(CommandHandler("request", self.request))
        self.__dp.add_handler(CommandHandler("cancel", self.cancel))
        self.__dp.add_handler(CommandHandler("show", self.show))
        self.__dp.add_handler(CommandHandler("promote", self.promote))
        self.__dp.add_handler(CommandHandler("demote", self.demote))
        self.__dp.add_handler(CommandHandler("checkadmin", self.check_admin))
        self.__dp.add_handler(CommandHandler("kick", self.kick))
        self.__dp.add_handler(CommandHandler("stop", self.stop_all))
        self.__dp.add_handler(CommandHandler("whatsmyid", self.__whatsmyid))
        self.__updater.start_polling()

    def start_message(self, update, context):
        """
        /start
        When a user starts a connection with a bot, the user will automatically send a message /start
        this commands sends the greeting message to the user and explains him how to use the service
        :param update: update - an update regarding the information of the message
        :return: None
        """

        user = self.User(update)
        output = "Greetings, we're happy that you decided to join and use the Bus4U service!\n" \
                 "in order to see all the possible commands you can type /help\n" \
                 "Also we want you to know that every command that you type and the server response will" \
                 "be logged and you can access your history with /history.\n\n" \
                 "we hope you'll enjoy the product and wish you the best.\n Never Miss a Bus."
        user.send_message(output)
        self.data_base.log(user, "*Showed Greeting Message*")

    def stop_all(self, update, context):
        """
        Syntax: /stop
        Admin only command
        Stops all the server
        :param update: update - an update regarding the information of the message
        :return: None
        """

        user = self.User(update)
        if not self.data_base.check_admin(user):  # allow access only to admins.
            output = "you cannot access this command, must be an admin"
            self.data_base.log(user, update.message.text, output)
            user.send_message(output)
            return
        message = update.message.text.lower().split(" ")
        if len(message) != 2:
            output = "you must type the full command to stop the server\n" \
                     "try /stop server\n" \
                     "USE ONLY IF YOU MUST"
        elif update.message.text.split(" ")[1] != "server":
            output = "You typed the wrong command.\n" \
                     "If you are sure that you want to stop the server type /stop server\n" \
                     "USE ONLY IF YOU MUST"
        else:
            output = "Stopping server."
            print("stopping by remote request from the Telegram admins.")
            self.__gui.remote_stop = True  # has to be done this way so the threads don't interfer with tkinter.
        self.data_base.log(user, update.message.text, output)
        user.send_message(output)

    def help(self, update, context):
        """
        /help
        Accessible to all, but will show more commands to admins
        the log won't see everything but only *helped* so it won't be spammed
        :param update: update - an update regarding the information of the message
        :return: None
        """

        message = update.message.text.lower().split(" ")
        user = self.User(update)
        if len(message) > 1 and message[1] == "me":
            output = 'if you need help buddy, call 1201 they are good guys and they will help you'
        else:
            """Send help when the command /help is issued."""
            output = '/request {line} {station} \n' \
                     '/history show/clear\n' \
                     '/show\n' \
                     '/cancel {line} {station}\n' \
                     '/help'

            if self.data_base.check_admin(user):
                output += '\n\n--admin commands --\n' \
                          '/kick\n' \
                          '/promote {me/id}\n' \
                          '/demote {me/id}\n' \
                          '/stop'
        update.message.reply_text(output)
        self.data_base.log(user, update.message.text, "*helped*")

    def __whatsmyid(self, update, context):
        """
        one of the commands accessible to everyone, but it won't be shown to everyone in help
        displays the Telegram id of the user
        syntax: /whatsmyid
        used when trying to promote a member to be an admin
        will be censored in history logs so the ID won't be accessible if anyone hacks the database
        later will be used in /promote {id}
        """
        user = self.User(update)
        output = f"your ID is: {user.id}"
        user.send_message(output)
        self.data_base.log(user, update.message.text, "*" * len(str(user.id)))

    def show(self, update, context):
        """
        /show lines - shows all the lines in the system
        /show buses for line {line number} - shows the locations of all the buses in the system
        /show requests - shows all the active requests that the user has

        one of the commands accessible to everyone
        :param update: update - an update regarding the information of the message
        :return: None
        """

        # TODO: add show how long till bus
        message = update.message.text.lower().split(" ")
        user = self.User(update)
        if len(message) == 1:
            output = "hey looks like you still don't know how to use this command\n" \
                     "don't worry, I'll teach you :)\n" \
                     "here's a list of what you can do:\n" \
                     "/show requests - this will show you your pending requests\n" \
                     "/show lines - this will show you the lines that are available\n" \
                     "/show buses for line {number} - this will show you the locations of the buses in the line you've specified"
        elif message[1] == "lines":
            print("showing lines")
            available_lines = self.bus_controller.show_available_lines()
            if available_lines == "None":
                output = "there are currently no available lines"
            else:
                output = f"the currently available lines are: {str(available_lines)}"
        elif message[1] == "requests":
            user = self.__find_matching_user(user)
            if len(user.stations) == 0:
                output = "You don't have any pending requests"
            else:
                output = "Your pending requests:\n"
                for station in user.stations:
                    output += f"{station}\n"
                output = output[:-1:]
        elif message[1:-1:] == ['buses', 'for', 'line']:
            if not message[4].isnumeric():  # checks that the value is a number
                output = f"{message[4]} isn't a number i support, therefor I can't help you."
            elif not (int(message[4]) > 0 and int(message[4]) <= 999):  # checks that the number is within limits
                output = f"sorry, {message[4]} is out of range, we only have lines within the range 1-999"
            else:  # gets here if the number is legit and everything is good
                line_num = int(message[4])
                if not self.bus_controller.check_line(line_num):
                    output = "there are no available buses for that line"
                else:
                    output = f"the locations of the buses that are available for that line are: \n" \
                             f"{self.bus_controller.show_buses_for_line(line_num)}"
        else:
            print(message[1:-1:])
            output = "couldn't recognise this command, try /show for the list of options you have for this command"
        self.data_base.log(user, update.message.text, output)
        user.send_message(output)

    def notify_passengers_about_incoming_bus(self, bus):
        """
        Tells all the passengers waiting for that line that their bus is arriving soon.
        For example: "Dear Idan pog, your bus line 45 will soon arrive at your station."
        :param bus: BusController.Bus
        :return: None
        """

        for user in self.__find_relevant_passengers(bus.line_num, bus.station_num + 1):
            user.send_message(
                f"Hey {user.name.split(' ')[0]} your bus line {bus.line_num} will arrive soon at your station.")

    def broadcast_to_users(self, text: str, sending_group):
        """
        Broadcasts to the sending group a message from the server.
        takes a string, and sends out the message to all the users in form of "broadcast from the server: {text}"
        :param text: str
        :param sending_group: str/int
        :return: None
        """
        if sending_group == "global":
            for user in self.__users.values():
                user.send_message(f"broadcast from the server: {text}")
            print("in broadcast to users global")
        elif sending_group.isdigit():
            sending_group = int(sending_group)
            for user in self.__users.values():
                for station in user.stations:
                    if station.line_number == sending_group:
                        user.send_message(f"broadcast from the server: {text}")
            print(f"in broadcast to users line{sending_group}")

    def __find_relevant_passengers(self, line: int, station_num: int):
        """
        internal command
        :param line: int
        :param station_num: int
        :return: a list that contains all the passengers that are waiting at the given station.
        """
        output = []
        for user in self.__users.values():
            for station in user.stations:
                if station.line_number == line and station.station_number == station_num:
                    output.append(user)
        return output

    def remove_everyone_from_station(self, line: int, station_num: int):
        """
        deletes all the users waiting at the certain station, and gives a list of users that have been kicked
        :param line: int
        :param station_num: int
        :return: a list with all the users that need to be removed.
        """
        removed_users = []
        for user in self.__users.values():
            for station in user.stations:
                if station.line_number == line and station.station_number == station_num:
                    removed_users.append(user)
        for user in removed_users:
            self.__users.pop(user.id)
        # map( )
        return removed_users


    def promote(self, update, context):
        """
        /promote {id}
        command accessible to admins only
        promotes the requested user
        :param update: update - an update regarding the information of the message
        :return: None
        """

        message = update.message.text.lower().split(" ")
        user = self.User(update)
        if not self.data_base.check_admin():
            output = "This command is only accessible to admins"

        elif len(message) == 2:
            if not self.data_base.check_admin(id=message[1]):
                self.data_base.promote_admin(id=message[1])
                output = f"Promoted user with ID: {message[1]} to Admin role."
            else:
                output = "The user you're trying to Promote is already an admin"
        else:
            output = "you might have made a syntax mistake, the correct form of promoting someone is /promote {his id number}"

        self.data_base.log(user, update.message.text, output)
        user.send_message(output)

    def demote(self, update, context):
        """
        command accessible to admins only
        demotes the requested user
        syntax: /demote {me/id}
        :param update: update - an update regarding the information of the message
        :return: None
        """
        message = update.message.text.lower().split(" ")
        user = self.User(update)
        output = ""
        if not self.data_base.check_admin():
            output = "This command is only accessible to admins"
        elif len(message) != 2:
            output = "You might have made a syntax mistake, the correct form of demoting someone is /demote {his id number}"
        elif message[1] == "me":
            if self.data_base.check_admin(user):
                self.data_base.demote_admin(user)
                output = "Congratulations sir, you're no longer an Admin."
            else:
                output = "Cannot demote, you're already a regular user."
        else:
            if self.data_base.check_admin(id=message[1]):
                self.data_base.demote_admin(id=message[1])
                output = f"Demoted user  with ID: {message[1]} from Admin role."
            else:
                output = "The user you're trying to demote isn't an admin."
        user.send_message(output)
        self.data_base.log(user, update.message.text, output)

    def check_admin(self, update, context):
        """
        /checkadmin
        the command is accessible to everyone, but won't be shown in help
        used to check if the user has admin permissions.
        sends the user (True/False)
        :param update: update - an update regarding the information of the message
        :return: None
        """

        user = self.User(update)
        output = self.data_base.check_admin(user)
        user.send_message(output)
        self.data_base.log(user, update.message.text, str(output))

    def history(self, update, context):
        """
        /history show - shows the history
        /history clear - clears all the records of the user history.
        the command is accessible to everyone
        used to manage the history of the account.
        :param update: update - an update regarding the information of the message
        :return: None
        """

        message = update.message.text.lower().split(" ")
        user = self.User(update)
        output = ""
        if message[1] == "show":
            if not self.data_base.has_history(user):
                output = "you don't have any history"
                self.data_base.log(user, update.message.text, output)
            else:
                output = self.data_base.show_history(user)
                if len(output) > 4096:
                    output = output[-4096::]
                self.data_base.log(user, update.message.text, "Successfully  showed history")

        if message[1] == "clear":
            if not self.data_base.has_history(user):
                output = "your history is already clean"
            else:
                self.data_base.clear_history(user)
                output = "Clean"
            self.data_base.log(user, update.message.text, output)
        user.send_message(output)

    def request(self, update, context):
        """
        /request {line} {station}
        the command is accessible to everyone
        places a request for the bus and notifies everyone needed.
        :param update: update - an update regarding the information of the message
        :return: None
        """

        user = self.User(update)
        user = self.__find_matching_user(user)
        message = update.message.text.lower().split(" ")
        if len(message) != 3:
            output = "looks like you have a little mistake in the command\n" \
                     "try /bus {bus number} {station number}" \
                     "for example /bus 14 3"
        else:
            try:
                line = int(message[1])
                station = int(message[2])
                if len(user.stations) >= 3 and not self.data_base.check_admin(user):
                    output = "Sorry you cannot have more than 3 requests at a time."
                elif line in map(lambda x: x.line_number, user.stations) and not self.data_base.check_admin(user):
                    station_to_cancel = "Error"
                    for station in user.stations:
                        if station.line_number == line:
                            station_to_cancel = station.station_number
                    output = "looks like you already have a request for that line so you cannot place another one\n" \
                             f"if that was a mistake you can cancel your request with /cancel {line} {station_to_cancel}"
                elif line <= 0 or line > 999:
                    output = f"line {line}, doesn't exist. try a line withing the range of 1-999"
                elif station <= 0 or station > BusController.MAX_STATION:
                    output = f"station {station}, doesn't exist. try a station withing the range of 1-{BusController.MAX_STATION}"
                elif self.bus_controller.check_line(line):
                    self.bus_controller.add_person_to_the_station(line, station)
                    output = f"request accepted, the bus is notified"
                    self.__message_sender.send_line(line, update_passengers=True)
                    self.__add_to_users_dict(update)
                else:
                    self.bus_controller.add_person_to_the_station(line, station)
                    output = f"request accepted, but there are no buses available for that line yet"
                    self.__add_to_users_dict(update)
            except Exception as e:
                print(e)
                output = "both of the values you give must be number in order to work" \
                         "for example, /bus 14 3"

        self.data_base.log(user, update.message.text, output)
        update.message.reply_text(output)

    def __find_matching_user(self, user):
        """
        Internal command
        Returns the user with the matching ID out of the self.__users dict.
        if it doesn't find one then it just returnes the user that it recieved
        :param user: TelegramController.User - a user that needs to find a match
        :return: TelegramController.User
        """
        if not user.id in self.__users.keys():
            return user
        return self.__users[user.id]

    def cancel(self, update, context):
        """
        /cancel {line} {station}
        One of the commands accessible to everyone
        Used to cancel requests for buses
        Sends the user an update if it managed to cancel everything or it failed somewhere
        :param update: update - an update regarding the information of the message
        :return: None
        """

        output = ""
        user = self.User(update)
        message = update.message.text.lower().split(" ")
        print(message[1], message[2])
        if user.id not in self.__users.keys():
            output = "looks like you don't have any requests at all."
        elif message[1].isnumeric() and message[2].isnumeric():
            user = self.__users[user.id]
            line_num = int(message[1])
            station_num = int(message[2])
            found_match = False
            for station in user.stations:
                if station.line_number == line_num and station.station_number == station_num:
                    user.remove_station(station)
                    self.bus_controller.remove_person_from_the_station(station)
                    output = "Canceled the request"
                    found_match = True
                    break
            if not found_match:
                output = "this doesn't match with any of your active requests, so you can't cancel it.\n" \
                         "make sure that you don't have any typing mistakes"
        else:
            output = "the values you entered seem wrong, the values must be number."
        self.data_base.log(user, update.message.text, output)
        user.send_message(output)

    def kick(self, update, context):
        """
        /kick buses - kicks all buses out of the system
        /kick people - kicks all the passengers out of the system
        only accessible to admins
        used to kick the buses or the passengers from the system remotely
        :param update: update - an update regarding the information of the message
        :return: None
        """

        user = self.User(update)
        if not self.data_base.check_admin(user):
            output = "you cannot access this command, must be an admin"
            self.data_base.log(user, update.message.text, output)
            user.send_message(output)
            return

        message = update.message.text.lower().split(" ")
        if message[1] == "buses":
            if len(self.bus_controller.bus_dict) == 0:
                output = "there are already no buses in the system"
            else:
                self.bus_controller.kick_all_buses()
                output = "kicked all buses"

        elif message[1] == "people":
            self.kick_all_passengers("kicked all users by an admin")
            output = "successfully kicked all the passengers"
        else:
            output = "unrecognized command. try /kick buses or /kick people"
        self.data_base.log(user, update.message.text, output)
        user.send_message(output)

    def kick_all_passengers(self, reason: str):
        """
        internal command
        sends to all the passengers a message that tells them they've been kicked for {reason}
        if they've been kicked after the button press from the server then a custom message will be sent that looks nicer
        at the end deletes all the users from the self.__users dict. and tells the bus controller as well to kick all the users
        :param reason: str
        :return: None
        """

        for user in self.__users.values():
            if reason == "kicked all passengers by an admin":  # the ususal case, made a standart message so users won't be nervous
                user.send_message(
                    f"Hello {user.name.split(' ')[0]}, your request has been removed.\n"
                    f"Simply place another one if it's still relevant.\n\nBest regards, Bus4U team")

            else:  # in case of something spacial
                print(f"reason '{reason}'")
                user.send_message(
                    f"hello {user.name.split(' ')[0]}, it looks like you've been kicked out of the system for: {reason}")

        self.__users = {}
        self.bus_controller.kick_all_passengers()

    def __kick_passenger(self, user, reason):
        """
        internal command
        kicks a {user} for a {reason}
        :param user: TelegramController.User
        :param reason: str
        :return: None
         """

        try:
            if user.id not in self.__users.keys():
                print("the person you're trying to delete doesn't exist.")
                return

            if reason == "kicked all passengers by an admin":  # the ususal case, made a standart message so users won't be nervous
                user.send_message(
                    f"Hello {user.name.split(' ')[0]}, your request has been removed.\n"
                    f"Simply place another one if it's still relevant.\n\nBest regards, Bus4U team")

            else:  # in case of something spacial
                print(f"reason '{reason}'")
                user.send_message(
                    f"hello {user.name.split(' ')[0]}, it looks like you've been kicked out of the system for: {reason}")
            del self.__users[user.id]
        except Exception as e:
            print("Some Error accrued")


    def __add_to_users_dict(self, update):
        """
        Internal command
        Creates a User instance, if there is a user with a matching ID in the self.__users
        then the user in the dictionary will be added another station to the stations storage.
        :param update: update - an update regarding the information of the message
        :return: None
        """

        message = update.message.text.lower().split(" ")
        line_num = int(message[1])
        station_num = int(message[2])
        station = self.Station(line_num, station_num)
        user = self.User(update)
        user.add_station(station)
        if user.id in self.__users.keys():
            self.__users[user.id].add_station(station)
        else:
            self.__users[user.id] = user


    class Station:
        """
        Internal class used to represent a stations.
        holds s a line number and a station number.
        """

        def __init__(self, line_number, station_number):
            """
            :param line_number: str/int
            :param station_number:  str/int
            """
            self.__line_number = int(line_number)
            self.__station_number = int(station_number)

        def __str__(self):
            """
            :return: str
            """
            return f"line number: {self.__line_number},  station_number: {self.__station_number}"

        @property
        def line_number(self):
            """
            :return: int
            """
            return self.__line_number

        @property
        def station_number(self):
            """
            :return: int
            """
            return self.__station_number

    class User:
        """
        Represents a user, a passenger that communicates with the server through the telegram bot
        can send a message to the user if needed
        remembers all the stations that the user has requested in the past.
        knows information about the user that is acquired from the telegram
        """

        def __init__(self, telegram_info: object) -> object:
            """
            :param telegram_info: update - holds all the information regarding the user
            :return: TelegramController.User
            """

            self.__telegram_info = telegram_info
            self.__stations = []

        def add_station(self, station):
            """
            gets a station and just adds it to the list of stations that the user has requested
            :param station: TelegramController.Station
            :return: None
            """
            self.__stations.append(station)

        def remove_station(self, station):
            """
            gets a station and just removes it from the list of stations that the user has requested
            :param station: TelegramController.Station
            :return: None
            """
            self.__stations.remove(station)

        def send_message(self, text):
            """
            sends a message to the user
            :param text: str
            :return: None
            """
            self.__telegram_info.message.reply_text(text)

        @property
        def stations(self):
            """
            :return: list
            """
            return self.__stations

        @property
        def telegram_info(self):
            """
            :return: update
            """
            return self.__telegram_info

        @property
        def id(self):
            """
            :return: str
            """
            return self.__telegram_info.message.from_user.id

        @property
        def name(self):
            """
            returns the full name of the user, for example "Idan pog"
            makes the first letter a capital letter
            :return: str
            """
            name = self.__telegram_info.message.from_user.name
            return name[0].upper() + name[1::]


class DBManager:
    """
    The DBManager is responsible for all the information stored about the users
    including their history, and their rank.
    User id's encrypted using the md5 function with a custom key
    """

    def __init__(self):
        """
        allocates place for all the important things that will be used later
        :return: DBManager
        """

        self.__path = "DataBase.db"
        self.__admins = []
        self.__banned = []
        self.__update_admin_cache()

    def has_history(self, user):
        """
        Returns True if the user has history in the server, False if not.
        :param user: User
        :return: bool
        """

        header = connect(self.__path)
        curs = header.cursor()
        encrypted_id = md5((str(user.id) + "typicaluser").encode()).hexdigest()
        curs.execute("SELECT * FROM users WHERE id = (?)", (encrypted_id,))
        data = curs.fetchall()
        return len(data) >= 1

    def show_history(self, user: TelegramController.User):
        """
        returns the user's full history record.
        :param user: User
        :return: str
        """

        header = connect(self.__path)
        curs = header.cursor()
        encrypted_id = md5((str(user.id) + "typicaluser").encode()).hexdigest()
        curs.execute("SELECT * FROM users WHERE id = (?)", (encrypted_id,))
        data = curs.fetchall()[0][1]
        return data

    def clear_history(self, user: TelegramController.User):
        """
        clears all the history of the user sets it to ""
        :param user: TelegramController.User
        :return: None
        """
        header = connect(self.__path)
        curs = header.cursor()
        encrypted_id = md5((str(user.id) + "typicaluser").encode()).hexdigest()
        curs.execute("UPDATE users SET history = (?) WHERE id = (?)", ("", encrypted_id))
        header.commit()

    def log(self, user: TelegramController.User, input: str = "None", output: str = "None") -> NONE:
        """
        writes the new information into the data base, separated by lines that look like -----------------.
        :param user: User -  the refenced user
        :param input: str - the message that the user sent.
        :param output:  str - the output that the server returns
        :return: None
        """

        header = connect(self.__path)
        curs = header.cursor()
        encrypted_id = md5((str(user.id) + "typicaluser").encode()).hexdigest()
        if not self.has_history(user):
            curs.execute("INSERT INTO users VALUES(?, ?)", (encrypted_id, ""))

        curs.execute("SELECT * FROM users WHERE id = (?)", (encrypted_id,))
        data = curs.fetchall()[0][1]
        data += f"input: {input}\noutput: {output}\n" + "-" * 30 + "\n"
        curs.execute("UPDATE users SET history = (?) WHERE id = (?)", (data, encrypted_id))
        header.commit()

    def __update_admin_cache(self):
        """
        Part of the caching method that the program uses to increase performance.
        Each time the admin list changes in the data base this command is also called so the cached admin list will stay updated.
        Simply stores a copy of the admin list in the RAM memory.
        :return: None
        """

        header = connect(self.__path)
        curs = header.cursor()
        curs.execute("SELECT * FROM admins WHERE id IS NOT NULL")
        data = curs.fetchall()
        newlist = []
        for item in data:
            newlist.append(item[0])
        self.__admins = newlist

    def check_admin(self, user: TelegramController.User = None, id: str = None):
        """
        Used to check if the given User is an admin
        Has to get at least one of the required arguments to work properly.
        Uses the caching mechanism to increase performance
        :param user: User
        :param id: str
        :return: bool
        """

        if id == None:
            id = user.id

        return md5((str(id) + "admin").encode()).hexdigest() in self.__admins

    def promote_admin(self, user: TelegramController.User = None, id: str = None):
        """
        Will promote the given user to the admin rank and update the cache
        :param user: User - the user you're trying to promote
        :param id: str - the user's that you're trying to promote ID
        :return: None
        """

        if id == None:
            id = user.id
        header = connect(self.__path)
        curs = header.cursor()
        encrypted_id = md5((str(id) + "admin").encode()).hexdigest()
        curs.execute("INSERT INTO admins(id) VALUES(?)", (encrypted_id,))
        header.commit()
        self.__update_admin_cache()

    def demote_admin(self, user=None, id=None):
        """
        will demote the given user to the admin rank and update the cache
        :param user: User - the user you're trying to demote
        :param id: str - the user's that you're trying to demote ID
        :return: None
        """

        if id == None:
            id = user.id
        if self.check_admin(id=id):
            header = connect(self.__path)
            curs = header.cursor()
            encrypted_id = md5((str(id) + "admin").encode()).hexdigest()
            curs.execute("DELETE FROM admins WHERE id = (?)", (encrypted_id,))
            header.commit()
            self.__update_admin_cache()


class MessagesSender:
    """
    a class that takes care of sending updates to the buses
    works as a polling thread.
    each time someone needs to send a message he'll tell this class and the information will be added
    into the memory,  the SLEEP_TIME has passed it'll lock the data from changes, send the information and unlock it
    """

    SLEEP_TIME = 2  # in seconds  Must be smaller than the heartbeat sleep time

    def __init__(self):
        """
        initialize all the important variables
        :return: MessageSender
        """
        self.__bus_dict = None
        self.__passengers_dict = None
        self.__global_messages = dict()
        self.__line_messages = dict()
        # keys are line numbers, values contain an inner dict that contains 2 flags and 1 str, "update_passengers" "update_buses" "free_text" and each one will store important information
        self.__bus_messages = dict()
        # keys are line numbers, values store dicts containing the bus as a key, and the same dict as stored above (bool, bool, str)
        self.__global_messages_copy = str()
        self.__line_messages_copy = dict()
        self.__bus_messages_copy = dict()
        self.__buses_to_kick = list()
        # acquired later in code
        self.__lock_data = bool()
        self.__socket = None
        self.stop = bool()

    def connect(self, bus_controller):
        """
        Gains access to the bus_controller memory.
        Must be ran before the self.start() command is used
        :param bus_controller: BusController
        :return: None
        """

        self.__bus_controller = bus_controller

    def start(self):
        """
        validates that all the needed connections are made and the thread can be started
        starts the thread cycle, and gives starting values to variables.
        :return: None
        """

        if self.__bus_controller == None:
            print("can't start please pass me the needed dictionaries")

        self.__global_messages = {"kick reason": "", "free text": ""}
        self.__lock_data = False
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.stop = False
        __main_loop = threading.Thread(target=self.__main_loop, args=(), name="bus updater")
        __main_loop.start()


    """
    data senders, actually don't send anything but add it to the memory so the __main_loop will send it later.
    the logic is:
    check if something already exists regarding this sending group, if yes then add new data to it,
    if no then create new data dict with default values
    each sending group has a dictionary that stores the information that needs to be sent, the dict has 3 keys
    "passengers": bool      - will send the sending group an update regarding the state of all the passengers
    "buses": bool           - will send the sending group an update regarding the state of all the buses
    "free text": str        - will just send the free text
    "kick reason": str      - will just send the kick reason with a prefix "kicked for:{reason}"
    """
    def send_global(self, free_text: str = "", kick_reason=""):
        """
        allows to send messages to the global sending group
        :param free_text: str
        :param kick_reason: str
        :return: None
        """

        while self.__lock_data: #makes sure to not change the data while it's being proccessed and sent.
            sleep(0.01)

        if free_text != "":
            self.__global_messages["free text"] += free_text + ","

        if kick_reason != "":
            self.__global_messages["kick reason"] += kick_reason + ","
            bus_dict_copy = deepcopy(self.__bus_controller.bus_dict)
            for buses in bus_dict_copy.values():
                for bus in buses:
                    self.__buses_to_kick.append(bus)

    def send_line(self, line, update_buses: bool = False, update_passengers: bool = False, free_text: str = "",
                  kick_reason: str = ""):
        """
        sends a message to all the buses in the given line
        :param line: int
        :param update_buses: bool
        :param update_passengers: bool
        :param line: int
        :param free_text: str
        :param kick_reason: str
        :return: None
        """

        while self.__lock_data: # makes sure to not change the data while it's being proccessed and sent.
            sleep(0.01)
        if line in self.__line_messages.keys():
            self.__line_messages[line]["passengers"] = self.__line_messages[line]["passengers"] or update_passengers
            self.__line_messages[line]["buses"] = self.__line_messages[line]["buses"] or update_buses
            if free_text != "":
                self.__line_messages[line]["free text"] += free_text + "\n"
            if kick_reason != "":
                buses_copy = deepcopy(self.__bus_dict[line])
                for bus in buses_copy:
                    if bus not in self.__buses_to_kick:
                        self.__buses_to_kick.append(bus)
                self.__line_messages[line]["kick reason"] += kick_reason + "\n"


        else:
            self.__line_messages[line] = dict()
            self.__line_messages[line]["passengers"] = update_passengers
            self.__line_messages[line]["buses"] = update_buses
            self.__line_messages[line]["free text"] = ""
            self.__line_messages[line]["kick reason"] = ""
            if free_text != "":
                self.__line_messages[line]["free text"] = free_text + "\n"
            if kick_reason != "":
                self.__line_messages[line]["kick reason"] = free_text + "\n"


    def send_bus(self, bus, update_buses: bool = False, update_passengers: bool = False, free_text: str = "",
                 kick_reason: str = ""):
        """
        sends a message to a specific bus
        :param bus: BusController.Bus
        :param update_buses: bool
        :param update_passengers: bool
        :param free_text: str
        :param kick_reason: str
        :return: None
        """

        while self.__lock_data: # makes sure to not change the data while it's being proccessed and sent.
            sleep(0.01)
        if bus.line_num in self.__bus_messages.keys() and bus.id in self.__bus_messages[bus.line_num].keys():
            self.__bus_messages[bus.line_num][bus.id]["passengers"] = self.__line_messages[bus.line_num][bus.id][
                                                                          "passengers"] or update_passengers
            self.__bus_messages[bus.line_num][bus.id]["buses"] = self.__line_messages[bus.line_num][bus.id][
                                                                     "buses"] or update_buses
            if free_text != "":
                self.__bus_messages[bus.line_num][bus.id]["free text"] += free_text + "\n"
            if kick_reason != "":
                self.__bus_messages[bus.line_num][bus.id]["kick reason"] += kick_reason + "\n"
        else:
            self.__bus_messages[bus.line_num] = dict()
            self.__bus_messages[bus.line_num][bus.id] = dict()
            self.__bus_messages[bus.line_num][bus.id]["passengers"] = update_passengers
            self.__bus_messages[bus.line_num][bus.id]["buses"] = update_buses
            self.__bus_messages[bus.line_num][bus.id]["free text"] = ""
            self.__bus_messages[bus.line_num][bus.id]["kick reason"] = ""
            if free_text != "":
                self.__bus_messages[bus.line_num][bus.id]["free text"] = free_text + "\n"

            if kick_reason != "":
                self.__bus_messages[bus.line_num][bus.id]["kick reason"] = kick_reason + "\n"


    """
    Base Builders
    organizes the information stored in the dictionaries into str that the bus clients know to translate back into dictionaries
    """


    def __build_update_regarding_buses(self, line: int):
        """
        internal command
        builds an update regarding the buses out of the dictionary.
        in the form of: data  = "buses 1,3,7,9"
        the word buses and then the station numbers of all the buses in the line
        :param line: int
        :return: str
        """

        output = "buses:"
        for bus in self.__bus_controller.bus_dict[line]:
            output += f"{bus.station_num},"
            print(f"current output is {output}")
        return output[:-1:]

    def __build_update_regarding_passengers(self, line: int):
        """
        internal command
        builds an update regarding the buses out of the dictionary.
        In the form of: data  = "passengers 1-3,3-2,7-4,9-2"
        the word passengers followed by the pairs station_number-people_count separated by commas
        :param line: int
        :return: str
        """

        output = "passengers:"
        if line not in self.__bus_controller.stations_dict.keys():
            return output
        for station_number, people_count in self.__bus_controller.stations_dict[line].items():
            print(output)
            output += f"{station_number}-{people_count},"
        return output[:-1:]

    """
    Group Builders
    Each group builder builds a layer of information that later on will be combined into a message.
    Avoids sending the same data twice.
    The main message form looks like:
    buses 2,3,6,9\n
    people 2-5,4-9,9-1\n
    free text:The cake is a lie ;)
    """

    def __build_global_update(self):
        """
        builds the global layer message
        :return: str
        """

        if self.__global_messages_copy["free text"] != "":
            return f"free text:{self.__global_messages_copy['free text'][:-1:]}\n"
        return ""

    def __build_line_update(self, line):
        """
        builds a layer of information that's relevant only to the given line
        avoids collisions with the global layer
        :param line: int
        :return: str
        """

        output = ""
        if line not in self.__line_messages_copy.keys():
            return output

        if self.__line_messages_copy[line]["passengers"]:
            output += self.__build_update_regarding_passengers(line) + "\n"
        if self.__line_messages_copy[line]["buses"]:
            output += self.__build_update_regarding_buses(line) + "\n"
        if self.__line_messages_copy[line]["kick reason"] != "" and self.__line_messages_copy[line][
            "kick_reason"] not in self.__global_messages_copy["kick reason"]:
            output += f"kicked for:{self.__line_messages_copy[line]['kick reason']}" + "\n"
        if self.__line_messages_copy[line]["free text"] != "" and self.__line_messages_copy[line]["free text"] not in \
                self.__global_messages_copy["free text"]:
            output += "free text:" + self.__line_messages_copy[line]["free text"] + "\n"
        return output

    def __build_bus_update(self, bus):
        """
        builds a layer of data that's only relevant to the given bus
        avoids collisions with the line and global layers
        :param bus: BusController.Bus
        :return: str
        """

        output = ""
        if bus.line_num not in self.__bus_messages_copy.keys() or bus.id not in self.__bus_messages_copy[
            bus.line_num].keys():
            return output

        if self.__bus_messages_copy[bus.line_num][bus.id]["passengers"] and not self.__line_messages_copy[bus.line_num][
            "passengers"]:
            output += self.__build_update_regarding_passengers(bus.line_num) + "\n"

        if self.__bus_messages_copy[bus.line_num][bus.id]["buses"] and not self.__line_messages_copy[bus.line_num][
            "buses"]:
            output += self.__build_update_regarding_buses(bus.line_num) + "\n"

        if self.__bus_messages_copy[bus.line_num][bus.id]["free text"] != "" and not (
                self.__bus_messages_copy[bus.line_num][bus.id]["free text"] in self.__line_messages_copy[bus.line_num][
            "free text"] or
                self.__bus_messages_copy[bus.line_num][bus.id]["free text"] in self.__global_messages_copy["free text"]):
            output += "free text:" + self.__bus_messages_copy[bus.line_num][bus.id]["free text"] + "\n"

        return output

    def __main_loop(self):
        """
        Runs in a separated thread that keeps polling and sending the data.
        Builds 3 layers and adds them one onto the other.
        First handles the kicks and after that handles all the other data in the system.

        The first layer is global messages, just text, doesn't include any logic in it,
        Second layer is line messages, could be text, bus updates or passengers update, adds the needed information, doesn't overlap with the global layer,
        Third layer is bus messages, could be text, bus updates or passengers update, adds the needed information, doesn't overlap with line and global layer.
        At the end sends the notification to the bus
        greatly optimized to reduce the processing time when dealing with big amounts of buses at the server
        """

        while not self.stop:
            self.__lock_data = True
            self.__bus_messages_copy = deepcopy(self.__bus_messages)
            self.__line_messages_copy = deepcopy(self.__line_messages)
            self.__global_messages_copy = deepcopy(self.__global_messages)
            self.__bus_messages = {}
            self.__line_messages = {}
            self.__global_messages = {"kick reason": "", "free text": ""}
            buses_to_kick_copy = deepcopy(self.__buses_to_kick)
            self.__buses_to_kick = list()
            self.__lock_data = False

            for bus in buses_to_kick_copy:  # handles the buses that need to be kicked
                message = "kicked for reason:" + self.__global_messages_copy["kick reason"]
                if bus.line_num in self.__line_messages_copy.keys():
                    message += self.__line_messages_copy[bus.line_num]["kick reason"]
                if bus.line_num in self.__line_messages_copy.keys() and bus.id in self.__bus_messages_copy[
                    bus.line_num].keys():
                    message += self.__bus_messages_copy[bus.line_num][bus.id]["kick reason"]
                print(f"sending message{message.strip()}")
                bus.send_to_bus(message.strip())

            global_message = self.__build_global_update()
            for line, buses in self.__bus_controller.bus_dict.items():
                line_message = self.__build_line_update(line)
                for bus in buses:
                    bus_message = self.__build_bus_update(bus)
                    message = global_message + line_message + bus_message
                    message = message.strip("\n")
                    if message != "":
                        bus.send_to_bus(message)

            sleep(MessagesSender.SLEEP_TIME)

        self.__shut_down()
        print("polling thread stopped")

    def __shut_down(self):
        """
        Sends globally a message telling everyone that the server stopped.
        :return: None
        """

        for line, buses in self.__bus_dict.items():
            for bus in buses:
                bus.send_to_bus("Server Shut Down")


class BusController:
    """
    controls the buses and listens to inputs from them
    holds 3 important communication channels
    new_bus_connections = waits to receive connections from buses that want to join the system
    recieve_updates = waits for buses to send a message with an update regarding their location
    heart_beat = sends pulse to the bus client e very few seconds and if it doens't recieve an answer it kicks the bus

    when it's needed to send a notification to a bus, the BusController uses the MessageSender class as help.
    """

    NEW_CONNECTION_PORT = 8200
    STATIONS_PORT = 8201
    PASSENGERS_PORT = 8202
    HEART_BEAT_PORT = 8203
    HOST = socket.gethostbyname(socket.gethostname())
    PULSE_DELAY = 3  # in seconds
    MESSAGES_TTL = 10  # in seconds
    MAX_MESSAGES_TO_DISPLAY = 5
    MAX_STATION = 314

    @property
    def bus_dict(self):
        """
        a dictionary that holds all the information regarding the buses in the system
        each key is a line number and the value is a list that stores all the buses for this certain line number
        :return: dict
        """
        return self.__bus_dict

    @property
    def stations_dict(self):
        """
        a dictionary that holds all the information regarding the passengers that wait at the stations in the system
        each key is a line number and the value is another dictionary
        the inner dict holds the station number as a key and a number that represents how many people are waiting at the station.
        :return: dict
        """
        return self.__stations_dict

    @property
    def buses_count(self):
        """
        counts the total number of the buses in the system
        :return: int
        """

        count = 0
        for line in self.__bus_dict.values():
            # for item in buses:
            count += len(line)
        return count

    @property
    def bus_messages(self):
        """
        all living the messages that the bus drivers sent to the console admin.
        stores up to 1 message from each bus and and removes them after the TTL has passed
        :return: list
        """

        output = []
        for message in self.__bus_messages:
            if time.time() - message['time'] > BusController.MESSAGES_TTL:
                self.__bus_messages.remove(message)
            output.append(f"l{message['sender'].line_num}-s{message['sender'].station_num} sent: {message['text']}")
        while len(output)<BusController.MAX_MESSAGES_TO_DISPLAY:
            output.append("")
        return output

    def __init__(self):
        """
        :return: BusContoller
        """

        self.__new_bus_Socket = None     # used to accept and listen for new buses that join the system

        self.__bus_stations_Socket = None# used to get new updates from buses
        self.__ipv4 = str()
        self.__bus_dict = {}             # self.__bus_dict[line_num] holds an array that contains all the buses
        self.__stations_dict = {}        # self.__stations_dict[line_num][station] holds the amount of people at the station
                                         # it's a dictionary in a dictionary stracture
        self.__stop_threads = False      # used to stop all the threads in the server for proper shutdown
        self.__telegram_bot = None
        self.__message_sender = None
        self.__bus_messages = list()     # each message looks like {'sender': bus, 'time':time.time(), 'text': str()}

    def connect(self, telegram_bot, message_sender):
        """
        Used to get the needed connections with the outer work units.
        Must be ran before using the self.start() command.

        :param telegram_bot: TelegramBot
        :param message_sender: MessageSender
        :return: None
        """

        self.__telegram_bot = telegram_bot
        self.__message_sender = message_sender

    def start(self):
        """
        checks that the controller has all the needed connections
        launches all the important threads and gives starting values to variables
        new_bus_reviever - waits for connections from new buses and adds them to the system
        updates_tracker - waits for connections from buses in the system and updates the relevant information
        heart_beat - keeps track of all the buses and makes sure that there are no offline buses by kicking if found
        :return: None
        """

        self.__new_bus_Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__bus_stations_Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__ipv4 = (socket.gethostbyname(socket.gethostname()))
        if self.__telegram_bot == None:
            print("telegram bot connection is not set yet")
            return
        if self.__message_sender == None:
            print("message sender connection is not set yet")
            return
        new_bus_receiver = threading.Thread(target=self.__new_bus_reciever, args=(), name="new_bus_reciever")
        new_bus_receiver.start()
        updates_tracker = threading.Thread(target=self.__track_updates, args=(), name="updates_tracker")
        updates_tracker.start()
        heart_beat = threading.Thread(target=self.__heart, args=(), name="Heart beats")
        heart_beat.start()

    def stop(self):
        """
        stops the bus controller
        stops all the threads and prints into the log, (stopped)
        :return: None
        """

        self.__stop_threads = True
        self.__new_bus_Socket.close()
        self.__bus_stations_Socket.close()
        print(f"stopped {self}")

    def __track_updates(self):
        """
        waits for buses to update their location.
        will continue as long as self.__stop_threads = False
        accepts updates only from buses that already exist in the system, checks by id and ip match
        after every update, it will update all the buses about the change.
        """

        self.__bus_stations_Socket.bind((self.__ipv4, BusController.STATIONS_PORT))
        self.__bus_stations_Socket.listen(1)
        while not self.__stop_threads:
            # establish a connection
            try:
                message = "empty message"
                client_socket, addr = self.__bus_stations_Socket.accept()
                data = client_socket.recv(1024).decode()
                print(f"recieved {data}")
                if "message" in data:
                    line_num, station_num, id, keyword = data.split(":")[0].split(" ")
                    message = data.split(":")[1]
                else:
                    line_num, station_num, id = data.split(" ")

                if not (line_num.isdigit() and station_num.isdigit() and id.isdigit()):
                    print("some bus tried to access the system, but his ID doesn't match the expected")
                elif int(line_num) not in self.__bus_dict.keys() or id not in map(lambda bus: bus.id,
                                                                                  self.__bus_dict[int(line_num)]):
                    print("an unregistered bus tried to access the system, ignored.")
                elif "message" in data:

                    self.__bus_messages.append({
                        "sender": self.__find_bus_by_id(id),
                        "time": time.time(),
                        "text": message
                    })
                    if len(self.__bus_messages) > BusController.MAX_MESSAGES_TO_DISPLAY:
                        self.__bus_messages = self.__bus_messages[:-BusController.MAX_MESSAGES_TO_DISPLAY:]

                    print(f"recieved a message, added to the list: {self.__bus_messages}")
                else:

                    relevant_bus = self.__find_bus_by_id(id)
                    relevant_bus.set_station(station_num)
                    self.__telegram_bot.notify_passengers_about_incoming_bus(relevant_bus)
                    self.__try_remove_people_from_the_station(bus=relevant_bus)
                    if int(station_num) >= BusController.MAX_STATION:
                        self.remove_bus(relevant_bus)
                    self.__message_sender.send_line(int(line_num), update_buses=True)

            except Exception as e:
                print(f"exception in __track_updates: {e}")
                print("closed track_updates")

    def __find_bus_by_id(self, id: str, line_num: int = None):
        """
        Takes an id and retures the bus object with the matching id.
        If the optional param line_num is given it'll speed up the search.
        assumes that the bus is in the system and will return False in case of a error
        :param id:
        :param line_num:
        :return: BusController.Bus / bool
        """

        if line_num != None:
            for bus in self.bus_dict[line_num]:
                if bus.id == id:
                    return bus
        if line_num == None:
            for buses in self.__bus_dict.values():
                for bus in buses:
                    if bus.id == id:
                        return bus
        return False

    def __new_bus_reciever(self):
        """
        takes up a thread, runs in a loop until the flag self.__stop_threads set to True
        waits for new buses to log in the system
        adds them into the memory and updates everyone who needs to know about it.
        the required syntax from the bus side to join the system is data  = {line_number} {station} {ID}
        """

        print(f"waiting for buses at {self.__ipv4}:{BusController.NEW_CONNECTION_PORT}")
        self.__new_bus_Socket.bind((self.__ipv4, BusController.NEW_CONNECTION_PORT))
        self.__new_bus_Socket.listen(1)
        while not self.__stop_threads:
            # establish a connection
            try:
                client_socket, addr = self.__new_bus_Socket.accept()
                data = client_socket.recv(1024)
                # data  = {line_number} {station} {ID}
                line_num, station, ID = data.decode().split(" ")
                if int(station) < BusController.MAX_STATION:
                    bus = self.Bus(addr, line_num, station, ID)
                    self.__add_bus(bus)
                    self.__message_sender.send_bus(bus, update_passengers=True)
                    self.__message_sender.send_line(bus.line_num, update_buses=True)
                client_socket.close()
            except:
                print("closed the new_bus_reciever thread")
        print("closed the new_bus_reciever thread")

    def __add_bus(self, bus):
        """
        an internal method that adds the bus into the storage of the bus controller
        :param: BusController.Bus
        :return: None
        """

        if bus.line_num in self.__bus_dict:
            self.__bus_dict[bus.line_num].append(bus)
        else:
            self.__bus_dict[bus.line_num] = [bus, ]

    def add_person_to_the_station(self, line, station):
        """
        used only by outer classes that need to update the bus controller regarding a new user
        for example the telegram controller
        adds the user into the self.__stations_dict.
        :param line: int - the line that the person waits for
        :param station: int - the stations that the person waits at
        :return: None
        """

        if line in self.__stations_dict:
            if station in self.__stations_dict[line]:
                self.__stations_dict[line][station] += 1
            else:
                self.__stations_dict[line][station] = 1
        else:
            self.__stations_dict[line] = {station: 1}

    def remove_person_from_the_station(self, station: TelegramController.Station):
        """
        removes the person from the station and notifies the buses about the update.
        :param station: TelegramController.Station
        :return: None
        """

        if station.line_number in self.__stations_dict and station.station_number in self.__stations_dict[
            station.line_number]:
            if self.__stations_dict[station.line_number][station.station_number] == 1:
                del self.__stations_dict[station.line_number][station.station_number]
                if len(self.__stations_dict[station.line_number]) == 0:
                    del self.__stations_dict[station.line_number]
            elif self.__stations_dict[station.line_number][station.station_number] > 1:
                self.__stations_dict[station.line_number][station.station_number] -= 1
            self.__message_sender.send_line(station.line_number, update_passengers=True)
        else:
            print("whoops an error, looks like the current station doesn't exit and there's no person waiting for it.")

    def __try_remove_people_from_the_station(self, line: int = None, station_num: int = None, bus=None):
        """
        takes a bus or a line and a station number instead
        checks if there are people waiting at the station, kicks them and all their other requests from the system
        when a person is picked up, all of his other requests also close.
        :param line: int
        :param station_num: int
        :param bus: BusController
        :return: None
        """

        if bus != None:
            line = bus.line_num
            station_num = bus.station_num
        if line not in self.__stations_dict.keys() or station_num not in self.__stations_dict[line].keys():
            return

        del self.__stations_dict[line][
            station_num]  # clears the Bus controller memory from users in the certain station
        if len(self.__stations_dict[line]) == 0:
            del self.__stations_dict[line]
        # launches a thread that waits one sec to notify the buses about the change in people, avoids collisions in TCP connections this way
        self.__message_sender.send_line(line, update_passengers=True)
        people_that_need_to_be_kicked = self.__telegram_bot.remove_everyone_from_station(line, station_num)
        # a list of Users that have been waiting at the station
        changed_lines = []
        for user in people_that_need_to_be_kicked:  # kick them from the memory of the bus controller
            for station in user.stations:
                if station.line_number != line:
                    self.remove_person_from_the_station(station)

    def show_available_lines(self):
        """
        just returns a list of all the active lines in the system
        :return: list
        """

        if len(self.__bus_dict) == 0:
            return "None"
        return list(self.__bus_dict.keys())

    def show_buses_for_line(self, line: int) -> str:
        """
        shows all the buses that are in the given line, shows the buses locations in the line.
        :param line: int
        :return: str
        """

        if line not in self.__bus_dict.keys():
            return "-None-"
        output = ""
        buses = self.bus_dict[line]
        for bus in self.bus_dict[line]:
            output += f"station: {bus.station_num}"
        return output

    def kick_all_buses(self, reason: str = ""):
        """
        tells all the buses that they've been kicked
        and then empties the self.__bus_dict
        :param reason: str
        return: None
        """

        self.__message_sender.send_global(kick_reason=reason)
        self.__bus_dict = {}
        print("kicked all buses from the system")

    def kick_all_passengers(self):
        """
        kicks all passengers
        notifies all the buses that the passengers have been removed
        :return: None
        """

        changed_lines = self.__stations_dict.keys()
        for line in changed_lines:
            if line in self.__bus_dict:
                self.__message_sender.send_line(line, update_passengers=True)
        self.__stations_dict = {}


    def __heart(self):
        """
        will be launched in a separate thread
        cycles the command pulse for all the buses every few seconds
        """

        while not self.__stop_threads:
            start_time = time.time()
            self.__pulse_all()
            # print(f"total pulse time = {time()-start_time} seconds")
            sleep(BusController.PULSE_DELAY)
        print("stopped the heartbeats")

    def __pulse_all(self):
        """
        pulses each bus with a "check" request, kicks the bus if he failed to pass the check
        crucial part of the heartbeat mechanism
        :return: None
        """

        if len(self.__bus_dict) == 0:
            return
        bus_dict_copy = self.__bus_dict.copy()
        for line in bus_dict_copy.values():
            for bus in line:
                self.__indevidual_pulse(bus)

    def __indevidual_pulse(self, bus):
        """
        will send the bus a message
        data = "Check"
        and wait for a response from the bus with his ID
        if the bus isn't responding, or sent the wrong ID he'll be kicked.
        """

        if not bus.check_up():
            print("bus found inactive")
            self.remove_bus(bus)

    def check_line(self, line):
        """
        returns wherever the line is in the server or not
        :param line: int
        :return: bool
        """
        return int(line) in self.__bus_dict

    def remove_bus(self, bus):
        """
        kicks a bus from the memory of the server, and notifies everyone who needs to know about it.
        :param bus: BusController.Bus
        :return: None
        """
        self.__bus_dict[bus.line_num].remove(bus)
        print(f"removed: {bus}")
        if len(self.__bus_dict[bus.line_num]) == 0:
            del self.__bus_dict[bus.line_num]

    class Bus:
        """
        an internal class that represents a bus.
        stores all the needed information including the line number, location, the ip and id
        """

        def __init__(self, address, line_number, station, ID):
            """
            :param address: tuple
            :param line_number: str
            :param station: str
            :param ID: str
            :return: BusController.Bus
            """

            self.__address = address
            self.__station = int(station)
            self.__line_number = int(line_number)
            self.__id = ID

        @property
        def station_num(self):
            """
            :return: int
            """
            return self.__station

        @property
        def line_num(self):
            """
            :return: int
            """
            return self.__line_number

        @property
        def id(self):
            """
            :return: str
            """
            return self.__id

        def set_station(self, station):
            """
            :param station: int
            :return: None
            """
            self.__station = int(station)

        def send_to_bus(self, data: str):
            """
            Sends the bus whatever information you give it
            :param data: str
            :return: None
            """

            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.__address[0], BusController.PASSENGERS_PORT))
            data = str(data).encode()
            s.send(data)
            s.close()

        def check_up(self):
            """
            part of the heartbeat mechanism
            send a Check notification
            returns True if everything is valid and false if the bus returned the wrong ID or didn't respond
            """

            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(BusController.PULSE_DELAY * 0.8)
            output = True
            start_time = time.time()
            try:
                s.connect((self.__address[0], BusController.HEART_BEAT_PORT))
                data = "Check".encode()
                s.send(data)
                data = s.recv(1024).decode()
                if int(data) != int(self.__id):
                    print(f"bus had the wrong ID\nwas supposed to be {self.__id}, but received {data}")
                    output = False
            # listen for an answer
            except Exception as e:
                print(f"exception in check_up (heart_beat) look:{e}")
                print(f"something went wrong, couldn't establish connection with {self.__address}")
                output = False
            s.close()
            return output

        def __str__(self):
            return f"line number: [{self.__line_number}], Current station [{self.__station}] \naddress: {self.__address}"


class GUI:
    """
    the Gui
    has buttons
        - kick all buses
        - kick all passengers
        - exit
    display that shows all the users in the system and the buses
    has some statistics as well
        - Number of active line
        - Number of buses in the system
        - Number of people waiting
    """

    def __init__(self):
        """
        initializes all the important information
        :return: GUI
        """

        self.__main_window = None
        self.__main_display_table = None
        self.remote_stop = False

        self.__start_time = None
        self.__broadcast_entry = None
        self.__broadcast_label = None
        self.__broadcast_button = None
        self.__active_lines_stringvar = None
        self.__active_buses_stringvar = None
        self.__number_of_people_stringvar = None
        self.__session_time_stringvar = None
        self.__free_text_stringvars_dict = dict() #holds all the stringvars needed for the bus messages
        self.__font_name = "Bahnschrift SemiBold SemiConden"
        #coordinates for groups of icons on the screen
        self.__main_buttons_coords = {"x": 458, "y": 647}
        self.__statistics_coords = {"x": 348, "y": 690}
        self.__admin_controls_coords = {"x": 459, "y": 777}
        self.__broadcast_coords = {"x": 22, "y": 356}
        self.__messages_coords = {"x": 58, "y": 56}
        self.__table_coords = {"x": 448, "y": 16, "width": 620, "height": 566}

    def connect(self, bus_controller, telegram_controller, message_sender, data_base):
        """
        Used to get the needed connections with the outer work units.
        Must be ran before using the self.start() command.

        :param bus_controller: BusController
        :param telegram_controller: TelegramController
        :param message_sender: MessageSender
        :param data_base: DBManager
        :return: None
        """

        self.__telegram_controller = telegram_controller
        self.__bus_controller = bus_controller
        self.__message_sender = message_sender
        self.__data_base = data_base

    def start(self):
        """
        starts the loading screen followed by the main window
        starts a loops that just keeps updeting all the widgets
        """

        self.__loading_window()
        self.__main_window = Tk()
        self.__start_time = time.time()
        self.__active_lines_stringvar = StringVar()
        self.__active_buses_stringvar = StringVar()
        self.__number_of_people_stringvar = StringVar()
        self.__session_time_stringvar = StringVar()
        for n in range(0, BusController.MAX_MESSAGES_TO_DISPLAY):
            self.__free_text_stringvars_dict[n] = StringVar()

        self.__background_img = ImageTk.PhotoImage(PIL.Image.open(r"Images server\main frame.png"))
        self.__main_window.geometry(f"{self.__background_img.width()}x{self.__background_img.height()}")
        self.__main_window.iconbitmap(r'Images server\childhood dream for project.ico')  # put stuff to icon
        self.__main_window.title("Control Panel")
        self.__main_window.resizable(OFF, OFF)
        Label(self.__main_window, image=self.__background_img, bg="#192b3d").place(x=0, y=0)
        self.__place_statistics_labels()
        self.__place_main_buttons()
        self.__place_broadcast_section()
        self.__place_bus_messages_section()
        self.__place_admin_controls()
        self.__place_table()

        self.__loop()
        self.__main_window.mainloop()

    @property
    def session_time(self):
        """
        tells how long the bus client has been running, telling how long the bus driver has been driving
        :return: str
        """

        time_in_seconds = time.time() - self.__start_time
        return time.strftime('%H:%M:%S', time.gmtime(time_in_seconds))

    def __loading_window(self):
        """
        starts the loading window, shows the logo and waits a set amount of time to let everything else load.
        NOT FINISHED YET
        :return: None
        """

        loading_window = Tk()
        loading_img = ImageTk.PhotoImage(PIL.Image.open(r"Images server\loading screen.png"))
        loading_window.geometry(f"{loading_img.width()}x{loading_img.height()-20}")
        loading_window.title("Loading")
        loading_window.resizable(OFF, OFF)

        loading_label = Label(loading_window, image=loading_img, bg="#192b3d")
        loading_label.place(x=0, y=0)
        loading_window.after(1000, lambda: loading_window.destroy())
        loading_window.mainloop()

    def __stop(self, reason="user"):
        """
        tries to close the window,
        after that tells the TelegramController unit and the BusControllerunit to stop
        takes an optional parameter that tells the other work units information about why the server stopped
        closes the code
        :param reason: str
        :return: None
        """

        print(f"trying to close because {reason}")
        try:
            self.__main_window.destroy()
        except:
            print("failed to close the main window")

        #self.__message_sender.stop = True          TO BE FIXED

        self.__telegram_controller.stop()
        self.__bus_controller.stop()
        sys.exit(f"properly closed by {reason}")

    def __kick_passengers(self):
        """
        tells the telegram controller unit to kick all the passengers
        passes the param reason that they have been kicked by an admin
        :return: None
        """

        self.__telegram_controller.kick_all_passengers("kicked all passengers by an admin")

    def __loop(self):
        """
        This is the main loop of the GUI, keeps everything updates and responsive
        As long as the variable stop = False it'll keep looping
        updates the table and the labels in the program
        """

        self.__update_table()
        self.__update_labels()
        if self.remote_stop:
            self.__stop("remote telegram admin")
        self.__main_window.after(1000, self.__loop)

    def __place_statistics_labels(self):
        """
        Places all the statistics lables
        Doens't take any parameters but uses that self.__statistics_coords to place the labels at the correct location
        :return: None
        """

        base_x = self.__statistics_coords["x"]
        base_y = self.__statistics_coords["y"]
        active_lines_label = Label(self.__main_window, textvariable=self.__active_lines_stringvar, fg="#1DB954", bg = "#000000", font = (self.__font_name, 18))
        number_of_buses_label = Label(self.__main_window, textvariable=self.__active_buses_stringvar, fg="#1DB954", bg = "#000000", font = (self.__font_name, 18))
        number_of_people_lable = Label(self.__main_window, textvariable=self.__number_of_people_stringvar, fg="#1DB954", bg = "#000000", font = (self.__font_name, 18))
        session_time_lable = Label(self.__main_window, textvariable=self.__session_time_stringvar, fg="#1DB954", bg = "#000000", font = (self.__font_name, 23))
        number_of_people_lable.place(x=base_x, y=base_y)
        active_lines_label.place(x=base_x-35, y=base_y + 35)
        number_of_buses_label.place(x=base_x+54, y=base_y + 69)
        session_time_lable.place(x=base_x-70, y=base_y + 116)

    def find_table_length(self):
        """
        An internal method that is used to search for how big the chart that displays the
        information about the buses and the passengers should be.
        finds the max len and returns it.
        :return: int
        """

        max_x_stations = 0
        for line_num, stations in self.__bus_controller.stations_dict.items():
            max_key = max(stations.keys())
            max_x_stations = max(max_key, max_x_stations)
        max_x_bus = 0

        for buses in self.__bus_controller.bus_dict.values():
            if len(buses) != 0:
                buses.sort(key=lambda bus: bus.station_num)
                max_x_bus = max(buses[-1].station_num, max_x_bus)
        max_x = max(max_x_bus, max_x_stations)
        return max_x

    def __update_table(self):
        """
        used to update the data on the display
        recalculates all the data again each time it's called
        still fast and reliable
        :return: None
        """

        headlines = ["", ]
        headlines += range(1, + 1)
        headlines = [" "] + [str(x) for x in range(1, self.find_table_length() + 1)]
        self.__main_display_table.config(columns=headlines)

        for headline in headlines:
            self.__main_display_table.heading(headline, text=headline)
            self.__main_display_table.column(headline, anchor="center", width=35)

        data = self.__display_buses_location()

        for i in self.__main_display_table.get_children():
            # deletes all the data in the chart
            self.__main_display_table.delete(i)
        for line in data:
            # inserts new data into the chart, goes line by line
            self.__main_display_table.insert("", END, values=line)


    def __update_labels(self):
        """
        updates all the with the new information
        generated the needed information and places it into the StringVars that are bound to the labels
        part of the main update loop that keeps everything updated
        :return: None
        """

        self.__active_buses_stringvar.set(str(self.__bus_controller.buses_count))
        self.__active_lines_stringvar.set(str(len(self.__bus_controller.bus_dict)))
        self.__number_of_people_stringvar.set(str(self.__telegram_controller.people_count))
        self.__session_time_stringvar.set(self.session_time)

        messages =self.__bus_controller.bus_messages
        for n in range(0, BusController.MAX_MESSAGES_TO_DISPLAY):
            self.__free_text_stringvars_dict[n].set(messages[n])

    def __place_table(self):
        """
        Places all the widgets related to the table, without placing any information in them.
        based on Ttk.Treeview, Ttk.Scrollbar and Ttk.ThemeStyle.
        the Ttk.ThemeStyle takes a long time to load so this causes almost all the waiting time for the loading of the program
        currently holds the Dark theme that makes the desgin match the outer desgin
        :return: None
        """

        base_x = self.__table_coords["x"]
        base_y = self.__table_coords["y"]
        base_height = self.__table_coords["height"]
        base_width = self.__table_coords["width"]
        headlines = [" "] + [str(x) for x in range(1, self.find_table_length() + 1)]
        #create a custome Style
        self.__tree_style = ThemedStyle(self.__main_window)
        self.__tree_style.set_theme("black")
        self.__tree_style.configure("mystyle.Treeview", highlightthickness=0, bd=0,
                        font=(self.__font_name, 11))  # Modify the font of the body
        self.__tree_style.configure("mystyle.Treeview", background="black",
                fieldbackground="black", foreground="green")
        self.__tree_style.configure("mystyle.Treeview.Heading", font=(self.__font_name, 13, 'bold'), foreground="green")  # Modify the font of the headings
        #creates the scrollbars
        scrollX = ttk.Scrollbar(self.__main_window, orient=HORIZONTAL)
        scrollY = ttk.Scrollbar(self.__main_window, orient=VERTICAL)
        self.__main_display_table = ttk.Treeview(self.__main_window, show="headings", columns=headlines,
                                             yscrollcommand=scrollY.set, xscrollcommand=scrollX.set, style = "mystyle.Treeview")
        #create a connection between the Tree and the Scrollbars and places them on the screen
        scrollY.config(command=self.__main_display_table.yview)
        scrollY.place(x=base_x + base_width, y=base_y, height=base_height)
        scrollX.config(command=self.__main_display_table.xview)
        scrollX.place(x=base_x, y=base_y + base_height, width=base_width)
        self.__main_display_table.place(x=base_x, y=base_y, width=base_width, height=base_height)
        #insert the headlines in to the table so there will be something to display as a starting value
        for headline in headlines:
            self.__main_display_table.heading(headline, text=headline)
            self.__main_display_table.column(headline, anchor="center", width=35)

    def __place_main_buttons(self):
        """
        Places the buttons, just at the first launch.
        depends on the self.__main_buttons_coords dict that tells where the buttons will be placed

        the buttons:
            - kick all buses
            - kick all passengers
            - stop server
        "return: None
        """

        #load the images and the locations
        base_x = self.__main_buttons_coords["x"]
        base_y = self.__main_buttons_coords["y"]
        self.__exit_btn_img = ImageTk.PhotoImage(PIL.Image.open(r"Images server\exit btn.png"))
        self.__kick_all_passengers_img = ImageTk.PhotoImage(PIL.Image.open(r"Images server\kick people btn.png"))
        self.__kick_all_buses_btn_img = ImageTk.PhotoImage(PIL.Image.open(r"Images server\kick buses btn.png"))
        #create the button objects and set their settings to match the desgin
        self.__kick_buses_btn = Button(self.__main_window, image=self.__kick_all_buses_btn_img, command=lambda: self.__bus_controller.kick_all_buses(reason="kicked all buses by the console"), borderwidth=0, background = "#000000", activebackground = "#083417")
        self.__kick__all_passengers_btn = Button(self.__main_window, image=self.__kick_all_passengers_img,command = lambda:self.__telegram_controller.kick_all_passengers("kicked all users from console"), borderwidth=0, background = "#000000", activebackground = "#083417")
        self.__exit_button = Button(self.__main_window, command=self.__stop, image=self.__exit_btn_img, borderwidth=0, background = "#000000", activebackground = "#B91D1D")
        #place the buttons on the screen
        self.__kick__all_passengers_btn.place(x=base_x, y=base_y)
        self.__exit_button.place(x=base_x+210, y=base_y+133)
        self.__kick_buses_btn.place(x=base_x + 210, y=base_y)

    def __place_broadcast_section(self):
        """
        Places the broadcast section widgets, just at the first launch.
        depends on the self.__broadcast_coords dict that tells where the buttons will be placed.

            Buttons:
            - global broadcast to buses - sends the message to all the buses
            - global broadcast to users - sends the message to all the users
            - line broadcast to buses - sends the message to only buses in the given line
            - line broadcast to users - sends the message to only users in the given line

            Entries:
            - global broadcast entry
            - line broadcast entry
            - line number

        :return: None
        """

        # load the images and the locations
        base_x = self.__broadcast_coords["x"]
        base_y = self.__broadcast_coords["y"]
        self.__send_to_buses_img = ImageTk.PhotoImage(PIL.Image.open(r"Images server\send to buses.png"))
        self.__send_to_people_img = ImageTk.PhotoImage(PIL.Image.open(r"Images server\send to people.png"))
        #create the button and entries objects and set their settings to match the desgin
        self.__global_broadcast_entry = Entry(self.__main_window, width=28, borderwidth=0, background="black",
                                              foreground="#1DB954", insertbackground="#1DB954",
                                              font=(self.__font_name, 22))
        self.__line_text_broadcast_entry = Entry(self.__main_window, width=28, borderwidth=0, background="black",
                                                 foreground="#1DB954", insertbackground="#1DB954",
                                                 font=(self.__font_name, 22))
        self.__line_number_broadcast_entry = Entry(self.__main_window, width=5, borderwidth=0, background="black",
                                                   foreground="#1DB954", insertbackground="#1DB954",
                                                   font=(self.__font_name, 16))
        self.__global_broadcast_to_buses_button = Button(self.__main_window, image=self.__send_to_buses_img,
                                                         command=lambda: self.__send_broadcast_to_buses(
                                                             sending_group="global"), borderwidth=0,
                                                         background="#000000", activebackground="#000000")
        self.__line_broadcast_to_buses_button = Button(self.__main_window, image=self.__send_to_buses_img,
                                                       command=lambda: self.__send_broadcast_to_buses(
                                                           sending_group="line"), borderwidth=0, background="#000000",
                                                       activebackground="#000000")
        self.__global_broadcast_to_people_button = Button(self.__main_window, image=self.__send_to_people_img,
                                                          command=lambda: self.__send_broadcast_to_users(
                                                              sending_group="global"), borderwidth=0,
                                                          background="#000000", activebackground="#000000")
        self.__line_broadcast_to_people_button = Button(self.__main_window, image=self.__send_to_people_img,
                                                        command=lambda: self.__send_broadcast_to_users(
                                                            sending_group="line"), borderwidth=0, background="#000000",
                                                        activebackground="#000000")
        #place the widgets on the screen
        self.__global_broadcast_entry.place(x=base_x, y=base_y)
        self.__line_text_broadcast_entry.place(x=base_x, y=base_y+143)
        self.__line_number_broadcast_entry.place(x = base_x +292, y= base_y+110)
        self.__global_broadcast_to_buses_button.place(x = base_x+3, y= base_y+54)
        self.__line_broadcast_to_buses_button.place(x = base_x+3, y= base_y+197)
        self.__global_broadcast_to_people_button.place(x = base_x+216, y= base_y+55)
        self.__line_broadcast_to_people_button.place(x=base_x + 216, y=base_y + 197)

    def __place_bus_messages_section(self):
        """
        creates and places all the needed widgets for the section that displays messages received from buses.
        needs to run just once.
        depends on the self.__messages_coords dict that tells where the buttons will be placed.
        creates BusController.MAX_MESSAGES labels and fill the self.__free_text_stringvars_dict with StringVars
        :return: None
        """

        base_x = self.__messages_coords["x"]
        base_y = self.__messages_coords["y"]
        spacing = 42
        self.__free_text_labels_dict = {}
        for n in range(0, BusController.MAX_MESSAGES_TO_DISPLAY):
            self.__free_text_labels_dict[n] =Label(self.__main_window, textvariable=self.__free_text_stringvars_dict[n], bg="#000000",
                                        fg="#1DB954", font=(self.__font_name, 16))
            self.__free_text_labels_dict[n].place(x= base_x, y = base_y + spacing*n)

    def __place_admin_controls(self):
        """
        Creates and places all the controlls related to promoting and demoting the users in the system

        includes:
            - promote button: promotes the given user upon click
            - demote button : demotes the given user upon clock
            - id entry      : a place to type the user id that you want to deal with
        :return: None
        """
        base_x = self.__admin_controls_coords["x"]
        base_y = self.__admin_controls_coords["y"]
        self.__admin_promote_img = ImageTk.PhotoImage(PIL.Image.open(r"Images server\promote btn.png"))
        self.__admin_demote_img = ImageTk.PhotoImage(PIL.Image.open(r"Images server\demote btn.png"))

        self.__admin_controls_entry = Entry(self.__main_window, borderwidth=0, width = 10,background = "black", insertbackground ="#1DB954",foreground="#1DB954", font = (self.__font_name, 29))
        self.__admin_promote_button = Button(self.__main_window, image=self.__admin_promote_img, command=self.__promote_admin_pressed, borderwidth=0, background = "#000000", activebackground = "#083417")
        self.__admin_demote_button = Button(self.__main_window, image=self.__admin_demote_img, command=self.__demote_admin_pressed, borderwidth=0, background = "#000000", activebackground = "#083417")

        self.__admin_controls_entry.place(x=base_x, y=base_y)
        self.__admin_promote_button.place(x=base_x + 100, y=base_y + 57)
        self.__admin_demote_button.place(x=base_x-3, y=base_y + 57)

    def __promote_admin_pressed(self):
        """
        an internal command.
        triggered upon self.__admin_promote_button click.
        gets the id from the entry, resets the entry back to the Empty state and promotes the user
        knows how to deal with invalid values.
        :takes information from self.__admin_controls_entry.get(): str
        :return: None
        """

        id = self.__admin_controls_entry.get()
        if not id.isdigit():
            print("failed to promote the user, the given id isn't a number")
            return
        self.__data_base.promote_admin(id=id)

    def __demote_admin_pressed(self):
        """
        an internal command.
        triggered upon self.__admin_demote_button click.
        gets the id from the entry, resets the entry back to the Empty state and demotes the user
        knows how to deal with invalid values.
        :takes information from self.__admin_controls_entry.get(): str
        :return: None
        """

        id = self.__admin_controls_entry.get()
        if not id.isdigit():
            print("failed to promote the user, the given id isn't a number")
            return
        self.__data_base.demote_admin(id=id)

    def __send_broadcast_to_buses(self, sending_group="global"):
        """
        An internal command
        Triggered upon self.__global_broadcast_to_buses_button or self.__line_text_broadcast_to_buses click.
        Gets the data to send from the self.__global_broadcast_entry or self.__line_number_broadcast_entry.
        in case of sending to line, it will get the line number from self.__line_number_broadcast_entry.
        :param sending_group: str - "global" / "line"
        return: None
        """

        if sending_group == "global":
            data = self.__global_broadcast_entry.get()
            self.__global_broadcast_entry.delete(0, 'end')
            self.__message_sender.send_global(free_text=data)

        elif sending_group =="line":
            line = self.__line_number_broadcast_entry.get()
            if len(line) > 0 and line.isnumeric():
                data = self.__line_text_broadcast_entry.get()
                self.__line_text_broadcast_entry.delete(0, 'end')
                self.__line_number_broadcast_entry.delete(0, 'end')
                self.__message_sender.send_line(int(line), free_text=data)
            else:
                print(f"line number must be a number, {line}")
        else:
            print(f"{sending_group} isn't a valid sending group")

    def __send_broadcast_to_users(self, sending_group="global"):
        """
        An internal command
        Triggered upon self.__global_broadcast_to_people_button or self.__line_text_broadcast_to_people_button click.
        Gets the data to send from the self.__global_broadcast_entry or self.__line_number_broadcast_entry.
        in case of sending to line, it will get the line number from self.__line_number_broadcast_entry.
        :param sending_group: str - "global" / "line"
        :return: None
        """

        if sending_group == "global":
            data = self.__global_broadcast_entry.get()
            self.__global_broadcast_entry.delete(0, 'end')
            print(f"broad casting data: {data}")
            self.__message_sender.send_global(free_text=data)

        elif sending_group == "line":
            line = self.__line_number_broadcast_entry.get()
            if len(line) >0 and line.isnumeric():
                data = self.__line_text_broadcast_entry.get()
                self.__line_text_broadcast_entry.delete(0, 'end')
                self.__line_number_broadcast_entry.delete(0, 'end')
                self.__telegram_controller.broadcast_to_users(data, sending_group=line)
            else:
                print(f"line number must be a number, {line}")
        else:
            print(f"{sending_group} is an invalid sending group")

    def __display_buses_location(self):
        """
        forms the list that contains all the information about the buses and the passengers.
        will display only the relevant lines.
        place a X to represent a bus and a number to represent a person
        :return: None
        """
        if len(self.__bus_controller.bus_dict) == 0 and len(self.__bus_controller.stations_dict) == 0:
            return [[]]  # breaks the run if there are no buses
        data = []
        empty_list = []  # an empty list that has placeholders for later use

        for i in range(self.find_table_length()):
            empty_list.append(" ")
        if len(self.__bus_controller.stations_dict) != 0:
            # makes sure that there are people waiting somewhere before we start marking them
            for line, stations in self.__bus_controller.stations_dict.items():
                list = [str(line)] + empty_list
                # creates the first line that has the placeholders and the line number
                for station, people_count in stations.items():
                    list[station] = people_count
                    # overrides the placeholders with the amount of people waiting at the station
                data.append(list)

        relevant_lines = []
        # just shows all the lines that are already in the list and showing passengers
        if len(self.__bus_controller.stations_dict) != 0:
            for list in data:
                relevant_lines.append(list[0])
        # buses override passengers if the collide at the same place
        for line, buses in self.__bus_controller.bus_dict.items():
            # puts an X wherever there's a bus
            if str(line) in str(relevant_lines):
                # if the line is already there it doesn't add another list into data
                for bus in buses:
                    data[relevant_lines.index(str(line))][bus.station_num] = "X"
            else:
                # if the line isn't there yet it adds another list that contains a placeholder and an X for each bus
                list = [str(line)] + empty_list
                for bus in buses:
                    list[bus.station_num] = "X"
                data.append(list)

        data = sorted(data, key=lambda list: int(list[0]))
        # sorts data by the first Value in the list so it would show the lines sorted.
        return data


def main():
    """
    start the server
    creates all the work units and gives them the needed connections and when ready luanch all of them
    """

    bus_controller = BusController()
    steve = TelegramController("990223452:AAHrln4bCzwGpkR2w-5pqesPHpuMjGKuJUI")
    message_sender = MessagesSender()
    db = DBManager()
    gui = GUI()

    message_sender.connect(bus_controller=bus_controller)
    bus_controller.connect(telegram_bot=steve, message_sender=message_sender)
    steve.connect(bus_controller=bus_controller, gui=gui, message_sender=message_sender, data_base=db)
    gui.connect(bus_controller=bus_controller, telegram_controller=steve, message_sender=message_sender, data_base=db)

    message_sender.start()
    bus_controller.start()
    steve.start()
    gui.start()


if __name__ == '__main__':
    main()
