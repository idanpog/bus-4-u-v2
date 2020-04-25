"""
author: Idan Pogrebinsky
2020
-- Bus Client --
"""

import random
import socket
import threading
import tkinter
from tkinter import ttk
from ttkthemes import ThemedStyle
from PIL import ImageTk
import PIL.Image
import time
from tkinter import *
from tkinter.ttk import Treeview


# TODO: fix all the access modifiers


class Bus:
    NEW_CONNECTION_PORT = 8200
    STATIONS_PORT = 8201
    PASSENGERS_PORT = 8202
    HEART_BEAT_PORT = 8203
    HOST = socket.gethostbyname(socket.gethostname())
    MAX_STATION = 14
    MAX_MESSAGE_COUNT = 2
    PULSE_DELAY = 5
    MESSAGE_TTL = 15
    # HOST = "192.168.3.11" #this client's IP
    ServerIP = "192.168.3.14"  # the server's IP


    def __init__(self, gui, id, line_number, station):

        """
        creates the object and assigns the objects starting values
        :param gui: GUI
        :param id: str
        :param line_number: int
        :param station: str
        :return: Bus
        """
        self.__id, self.__line_number, self.__station = id, line_number, int(station)
        self.__stations = {}
        self.__buses = []
        self.asking_user_to_reconnect = False
        self.__gui = gui
        self.stop = False
        self.__total_people_count = 0
        self.__starting_time = None
        self.__connected = None
        self.__kicked = False
        # holds all commands for the input handling from the server
        self.__data_handler = {"buses": self.__proccess_buses_chunk,
                               "passengers": self.__proccess_passengers_chunk,
                               "free text": self.__proccess_free_text_chunk,
                               "kicked for reason": self.__proccess_kick_chunk}
        #a list that holds dictionaries, each dictionary represends a message. holds "time" and "message" fields
        self.__server_free_text_messages = list(dict())
        self.__connection_established_time = None


    @property
    def connected(self):
        """
        tells wherever the bus is connected to the server or not
        :return: bool
        """
        return self.__connected

    @property
    def kicked(self):
        """
        tells wherever the bus is kicked from the server or not
        :return:  bool
        """
        return self.__kicked

    @property
    def total_people_count(self):
        """
        tells how many people in total are waiting for this line
        :return: int
        """
        return self.__total_people_count

    @property
    def session_time(self):
        """
        tells how much time has passed since bus logged into the system
        :return: str
        """
        session_time = int(time.time() - self.__starting_time)
        local_time = time.gmtime(session_time)
        return time.strftime('%H:%M:%S', local_time)

    @property
    def next_station_people_count(self):
        """
        tells how many people are waiting at the next station
        :return: int
        """
        if int(self.__station+1) in self.__stations.keys():
            return self.__stations[self.__station+1]

        return 0

    @property
    def server_free_text_messages(self):
        """
        returns the list that holds all the messages that the bus received from the server.
        :return: list that holds dictionaries
        """
        return self.__server_free_text_messages

    @property
    def max_number_of_stations(self):
        """
        returns how much of the table needs to be displayed, holds a minimum value.
        :return:
        """

        min_number_of_stations = 16
        biggest = max(self.__station, min_number_of_stations)
        if (len(self.__stations) != 0):
            biggest = max(max(self.__stations.keys()), biggest)
        if len(self.__buses) != 0:
            biggest = max(biggest, max(self.__buses))
        return biggest

    def start(self, first_attempt = True):
        """
        starts the connection between the server
        after that launches 2 threads, that keep the connection alive and keep track of relevant information

        if failed to connect to the server a window will be displayed saying that the connection failed and offer an
        option to try to reconnect.
        after a successful connection 2 threads will be started.
            - updates_tracking_thread: keeps track of updates received from the server (messages, passengers and more)
            - heartbeats_thread      : constantly answers the server's "check" requests, holds a timer that tells the
                bus that he's disconnected in case if it didn't receive a request from the server in a set amount of time

        :return: bool
        """

        try:
            self.__connect_to_server()
            self.__starting_time = time.time()
            update_tracking_thread = threading.Thread(target=self.__track_updates, args=(), name="updates_tracker")
            update_tracking_thread.start()
            heartbeats_thread = threading.Thread(target=self.__respond_to_heartbeats, args=(), name="heartbeats_thread")
            heartbeats_thread.start()
            return True
        except:
            self.__gui.failed_to_connect(first_attempt)
            return False

    def __respond_to_heartbeats(self):
        """
        Constantly answers the server's "check" requests, holds a timer that tells the
        bus that he's disconnected in case if it didn't receive a request from the server in a set amount of time.
        Tells the gui to display a lost connection message when needed.
        Doesn't stop trying to respond even if the bus is offline, it just skips the Pulse.
        :return: None
        """

        Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        Socket.bind((self.HOST, self.HEART_BEAT_PORT))
        Socket.listen(1)
        Socket.settimeout(Bus.PULSE_DELAY+1)
        while not self.stop:
            try:
                client_socket, addr = Socket.accept()
                data = client_socket.recv(1024).decode()
                if data == "Check":
                    client_socket.send(str(self.__id).encode())
            except:
                if time.time() - self.__connection_established_time < Bus.PULSE_DELAY+1:
                    print("connection is too young, skipping this heartbeat")
                else:
                    if self.__connected == True and not self.__kicked:
                        print("lost connection to the server")
                        self.__connected = False
                        self.__gui.display_lost_connection()
                    else:
                        print("still don't have connection to the server")

    def __connect_to_server(self):
        """
        tries to connect to the server by sending the default login message containing the relevant information for a login
        doesn't have fail protection - USE only in a try statement
        :return:  None
        """

        data = f"{self.__line_number} {self.__station} {self.__id}"
        Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print(f"trying to connect at {Bus.ServerIP}:{Bus.NEW_CONNECTION_PORT}")
        Socket.connect((Bus.ServerIP, Bus.NEW_CONNECTION_PORT))
        Socket.send(data.encode())
        Socket.close()
        self.__connection_established_time = time.time()
        self.__connected = True
        self.__kicked = False

    def __track_updates(self):
        """
        waits for updates at the Bus.PASSENGERS_PORT port from the server
        breaks down the data into chunks and passes them for processing into the data_handlers dict
        will continue as long as self.stop == False
        :return: None
        """

        while not self.stop:
            # establish a connection
            Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            Socket.bind((Bus.HOST, Bus.PASSENGERS_PORT))
            Socket.listen(1)
            try:
                client_socket, addr = Socket.accept()
                data = client_socket.recv(1024).decode()
                print(f"just got some new data, look '{data}'")
                data_chunks = data.split("\n")
                print(data_chunks)
                for data_chunk in data_chunks:
                    data_chunk = data_chunk.split(":")
                    chunk_type = data_chunk[0]
                    chunk_information = data_chunk[1]
                    print(f"chunk type {chunk_type}")
                    self.__data_handler[chunk_type](chunk_information)
            except Exception as e:
                print(f"exception in __track_updates: {e}")

            Socket.close()

    def __proccess_buses_chunk(self, chunk:str):
        """
        the processing unit that's responsible for taking care of information classified as buses from the server
        takes the data chunk and updates the memory regarding the buses
        chunk types classified as buses hold information regarding the locations of all the other buses in the system
        :param chunk: str
        :return: None
        """

        chunks = chunk.split(",")
        int_chunks = map(int, chunks) #converts the data from str to int
        self.__buses = list(int_chunks)#makes sure that the data is a list
        self.__buses.remove(self.__station) #removes the bus itself from his own display

    def __proccess_passengers_chunk(self, chunk:str):
        """
        the processing unit that's responsible for taking care of information classified as passengers from the server
        takes the data chunk and updates the memory regarding the passengers
        chunk types classified as passengers tell where and how many passengers are waiting for the bus.
        :param chunk: str
        :return: None
        """

        self.__stations = {}
        if len(chunk) == 0:
            return

        for station in chunk.split(","):
            station_number, people_count = station.split("-")
            self.__stations[int(station_number)] = int(people_count)

    def __proccess_free_text_chunk(self, chunk:str):
        """
        the processing unit that's responsible for taking care of information classified as free text from the server
        takes the data chunk and updates the memory regarding the free text received from the server.
        chunk types classified as free text hold messages from the server.
        :param chunk: str
        :return: None
        """

        for message in chunk.split(","):
            self.__server_free_text_messages.append({"text":message, "time": time.time()})
        if len(self.__server_free_text_messages) > Bus.MAX_MESSAGE_COUNT:
            self.__server_free_text_messages = self.__server_free_text_messages[-Bus.MAX_MESSAGE_COUNT::]

    def __proccess_kick_chunk(self, chunk:str):
        """
        the processing unit that's responsible for taking care of information classified as kicked for reason from the server
        takes the data chunk and updates tells the bus that it's kicked and shows the gui as well.
        chunk types classified as kicked for a reason: hold the reason why the bus has been kicked and are sent only when kicked.
        it's possible for future development to find a place to display th kick reason as well.
        :param chunk: str
        :return: None
        """

        self.__kicked = True
        self.__gui.display_kicked(chunk)

    def next_station(self):
        """
        sends an update to the server telling him that the bus has moved to the next station
        also update the station in the memory
        checks if the bus has finished his route and if he did updates the gui and pops a message telling the bus that he finished.
        a safe function, knows to handle loss of connection.
        :return: None
        """
        if self.__connected:
            try:
                data = f"{self.__line_number} {self.__station + 1} {self.__id}"
                self.__send_to_server(data)
                self.__station += 1
                if self.__station in self.__stations.keys():
                    self.__total_people_count += self.__stations[self.__station]
            except:
                self.__connected = False
                self.asking_user_to_reconnect = False

            if int(self.__station) + 1 > Bus.MAX_STATION:  # stop the bus client when he reaches his final station
                self.stop = True
                self.__gui.display_finished()
                return
        else:
            print("user trying to send update the server about change in the station but i am offline.")

    def send_free_text(self, free_text):
        """
        Sends the server a message from type free text, gets some free text and builds a message out of it
        Starts with the usual prefix and then adds another layer on top.
        :param free_text: str
        :return: None
        """

        data = f"{self.__line_number} {self.__station} {self.__id}"
        data +=f" message:{free_text}"
        return self.__send_to_server(data)

    def __send_to_server(self, data):
        """
        Sends the server the chunk of data that's given.
        doesn't do any processing, just sends it out.
        a safe function, doesn't crash but if it fails to send the message it'll update the self.__connected to False
        and pop a notification in the gui telling the driver that he lost connection to the server
        returns wherever the operation was successful or not
        :param data: str
        :return: bool
        """

        try:
            Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            Socket.connect((Bus.ServerIP, Bus.STATIONS_PORT))
            Socket.send(data.encode())
            Socket.close()
            return True
        except:
            self.__connected = False
            print("tried to send data to the server, but it appears as the connection cannot be established.\n"
                  f"aborted sending data to the server '{data}'")
            return False

    def display_passengers(self):
        """
        formulates a list that holds all the information to be displayed on the Table on top.
        takes into account passengers waiting, other buses in the system and the bus itself.
        passengers will be represented by a number,
        Other buses are represented with the word bus,
        the bus itself is represented with the word me.
        :return: list
        """

        list = [""]
        for i in range(self.max_number_of_stations + 1):
            list.append("")

        for station, count in self.__stations.items():
            list[station - 1] = str(count)

        for station in self.__buses:  #makes sure that the bus won't display itself twice
            list[station - 1] = "bus"

        list[self.__station - 1] = "me"

        return list

    def reconnect(self):
        """
        tried to reconnect to the server
        if the connection is succussful a message is printed out and True is returned
        in case if the connection fails, a message is printed and False is returned
        :return: bool
        """

        try:
            self.__connect_to_server()
            print("reconnected")
            return True
        except:
            print("failed to reconnect")
            return False

    def count_people(self):
        """
        counts all the people waiting for the bus and returns a number
        :return: int
        """

        return sum(self.__stations.values())

    def count_buses(self):
        """
        counts all the buses that work for the same line as this bus
        includes the bus itself in the count.
        :return:  int
        """

        return len(self.__buses) + 1


class GUI:
    """
    Graphical User Interface, makes the communication easier for the bus driver in order to reduce the time the
    driver has to put into communicating with the system.

    designed in a 3 color scheme, black, green, and white
    has a background glow thats used to show the bus driver important updates, that need his attention
    default color is green, changes the color to red when there's a passenger that needs to be picked up
    and changes the color to gray when the bus is offline.

    has a welcome window that his purpose is to acquire some information regarding the bus from the driver.
    3 entries that get the Bus ID, the line number and the starting station of the bus.
    And a Finish Button that saves the information and starts the bus system with the given information
    After the finish is clicked, the window will close and a loading screen is displayed while the main window is loading.

    the main window holds on top a display that shows the locations of all the relevant buses and passengers.
    Next Station button that moves the bus to the next station.
    a square with the purpose to make sure that the bus will stop at the station if there's a passengers.
    server broadcasts section that shows all the messages recieved from the server
    place to send messages to the server that consists of a send button and an entry to type the text into.
    also displays some statistics.
    and a big red exit button.
    """

    __BLACK = "#000000"
    __GREEN = "#105e29"
    __GREEN1 = "#1DB954"

    def __init__(self):
        """
        creates a GUI class instance
        :return: GUI
        """

        self.__line, self.__id, self.__station = None, None, None
        self.__bus = None
        self.__font_name = "Bahnschrift SemiBold SemiConden"
        self.__headlines = None
        self.asking_to_reconnect = False
        self.__passengers_count_stringvar = None
        self.__buses_count_stringvar = None
        self.__session_time_stringvar = None
        self.__server_broadbast_stringvars_dict = dict()
        #those dictionaries store the location regarding plament widget groups on the screen
        self.__statistics_coords = {"x": 540, "y": 408}
        self.__updating_statistics_coords ={"x": 680, "y": 331}
        self.__next_btn_coords = {"x": 29, "y": 177}
        self.__exit_btn_coords = {"x": 29, "y": 490}
        self.__broadcast_section_coords = {"x": 44, "y": 427}
        self.__server_messages_coords =  {"x": 66, "y": 326, "jump": 36}
        self.__table_coords = {"x": 26, "y": 74, "width" : 744, "height":59}


    def start(self):
        """
        starts the gui
        starts by asking for starting information for the bus, after that creates a bus instance with the given information
        after that starts the loading process for the rest of the program components.
        :return: None
        """

        self.config_first_data()
        if self.__line == None:
            sys.exit("Ended by user")


        self.__window = Tk()
        self.__window.iconbitmap(f'images bus\\icon.ico')  # put stuff to icon
        self.__window.title("Bus Client")
        self.__window.resizable(OFF, OFF)
        self.__start_loading_screen()
        self.__window.mainloop()
        self.stop()

    def stop(self):
        """
        stops the run of the gui and tells the bus to stop as well.
        at the end closes the code
        :return: None
        """

        self.__bus.stop = True
        try:
            self.__finished_window.destroy()
        except:
            print("finished window already closed.")
        try:
            self.__window.destroy()
        except:
            print("main window already closed.")
        sys.exit("closed by user")


    def __start_loading_screen(self):
        """
        Starts the loading proccess.
        At first shows the loading image, waits for 10ms and then
        starts loading all the widgets and the properties of the program.
        :return: None
        """

        loading_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\loading screen.png"))
        self.__window.geometry(f"{loading_img.width()}x{loading_img.height()}")
        self.__bg_label = Label(self.__window, image=loading_img, bg="#192b3d")
        self.__bg_label.place(x=0, y=0)
        self.__window.after(10, self.__finish_loading_screen)
        self.__window.mainloop()

    def __finish_loading_screen(self, launch_bus=True):
        """
        starts the bus object, places all the labels, buttons, data tables, entries
        and initializes all the values needed for the rest of the run
        :return: False
        """
        if launch_bus:
            self.__bus = Bus(self, self.__id, self.__line, self.__station)
            self.__bus.start()
        self.__headlines = [str(x) for x in range(1, self.__bus.max_number_of_stations + 1)]
        self.__passengers_count_stringvar = StringVar()
        self.__buses_count_stringvar = StringVar()
        self.__server_broadbast_stringvar1 = StringVar()
        self.__server_broadbast_stringvar2 = StringVar()
        self.__session_time_stringvar = StringVar()
        #init all the images
        self.__bg_nobody_is_waiting_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\nobody is waiting.png"))
        self.__bg_lost_connection_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\lost connection.png"))
        self.__bg_stop_at_the_next_station_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\stop at the next station.png"))
        self.__next_btn_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\next station.png"))
        self.__exit_btn_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\exit btn.png"))
        self.__send_btn_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\send btn.png"))
        #place the widgets on the window
        self.__create_table()
        self.__update_table()
        self.__place_buttons()
        self.__place_labels()
        self.__place_free_text_section()
        self.__window.geometry(f"{self.__bg_nobody_is_waiting_img.width()}x{self.__bg_nobody_is_waiting_img.height()}")
        self.__update_bg()
        #start the updates loop that will keep the widgets updated
        self.__loop()

    def __create_table(self):
        """
        creates and places the table that display the locations of the buses and the passengers for the line.
        uses the ttk. widgets Treeview combined with a scrollbar.
        and the ThemedStyle lib in order to give the dark themed look to the widget.
        :return: None
        """

        base_x = self.__table_coords["x"]
        base_y = self.__table_coords["y"]
        base_width = self.__table_coords["width"]
        base_height = self.__table_coords["height"]
        self.__tree_style = ThemedStyle(self.__window)
        self.__tree_style.set_theme("black")
        self.__tree_style.configure("mystyle.Treeview", highlightthickness=0, bd=0,
                                    font=(self.__font_name, 11))  # Modify the font of the body
        self.__tree_style.configure("mystyle.Treeview", background="black",
                                    fieldbackground="black", foreground="green")
        self.__tree_style.configure("mystyle.Treeview.Heading", font=(self.__font_name, 13, 'bold'),
                                    foreground="green")  # Modify the font of the headings
        scrollX = ttk.Scrollbar(self.__window, orient=HORIZONTAL)
        self.__tree = Treeview(self.__window, show="headings", columns=self.__headlines, xscrollcommand=scrollX.set, style = "mystyle.Treeview")
        self.__tree.place(x=base_x, y=base_y, width=base_width, height=base_height)
        scrollX.config(command=self.__tree.xview)
        scrollX.place(x=base_x, y=base_y+base_height, width=base_width)

    def __place_buttons(self):
        """
        Places the main buttons on the screen.
            next_button - tells the bus to move onto the next station and tell the server that he moved
            exit_button - closes the gui and the server
        :return: None
        """

        self.__next_button = tkinter.Button(self.__window, image=self.__next_btn_img, command=self.__bus.next_station, borderwidth=0, background = "#000000", activebackground = "#083417")
        self.__next_button.place(x=self.__next_btn_coords["x"], y=self.__next_btn_coords["y"])
        self.__exit_button = tkinter.Button(self.__window, command=self.stop, image=self.__exit_btn_img, borderwidth=0,
                                            background=GUI.__BLACK, activebackground=GUI.__BLACK, fg="red")
        self.__exit_button.place(x=self.__exit_btn_coords["x"], y=self.__exit_btn_coords["y"])

    def __update_labels(self):
        """
        updates all the labels in the program
            passenger count - shows how many passengers are waiting for the bus
            buses count - shows how many buses are active in the line
            session time - displays the session time of the driver
            server messages -  shows the messages received from the server

        updates the StringVars instead of recreating the label.
        the messages label is actually more than just 1 label, but all the labels and the StringVars are stored in the same dict
        the reason is that breaking down the messages into a couple layers allows more flexible formatting
        :return: None
        """

        #statistics
        self.__passengers_count_stringvar.set(str(self.__bus.count_people()))
        self.__buses_count_stringvar.set(str(self.__bus.count_buses()))
        self.__session_time_stringvar.set(f"{self.__bus.session_time}")
        #server messages
        messages = []
        for message in self.__bus.server_free_text_messages:
            if time.time() - message["time"] > Bus.MESSAGE_TTL: #Removes old messages
                self.__bus.server_free_text_messages.remove(message)
            messages.append(f"{time.strftime('%H:%M:%S', time.localtime(message['time']))}: {message['text']} \n")
        #makes sure that all the labels will be addressed, if there's not enough information for them fills with ""
        while len(messages) <Bus.MAX_MESSAGE_COUNT:
            messages.append("")
        #updates the StringVars
        for i in range(0,Bus.MAX_MESSAGE_COUNT):
            self.__server_broadbast_stringvars_dict[i].set(messages[i])

    def __loop(self):
        """
        the main GUI loop, run in the main thread and updates data on the screen (labels, table and background)
        runs twice per second but can be easily changes if needed
        will stop looping only when the self.__bus.stop is equal to True
        :return: None
        """

        if self.__bus.stop:
            return
        try:
            self.__update_table()
            self.__update_bg()
            self.__update_labels()
            self.__after_job = self.__window.after(500, self.__loop)
        except Exception as e:
            print(f"Done looping because: {e}")

    def __place_labels(self):
        """
        creates labels, configures them and places them at the places they're supposed to be.
        labels that are placed
            - passengers_count      shows the passengers count in the line
            - buses_count           shows the bus count of the buses in the line
            - server_messages       shows the messages received from the server
            - line_label            shows the line number
            - id_label              shows the bus id
            - session_time_label    shows the session time
        :return: None
        """

        # statistics labels
        self.__passengers_count_stringvar.set(str(self.__bus.count_people()))
        self.__buses_count_stringvar.set(str(self.__bus.count_buses()))
        #changing statistics
        base_x = self.__updating_statistics_coords["x"]
        base_y = self.__updating_statistics_coords["y"]
        passengers_count_label = Label(self.__window, textvariable=self.__passengers_count_stringvar, fg=GUI.__GREEN,
                                       bg=GUI.__BLACK, font=(self.__font_name, 13, "bold"))
        buses_count_label = Label(self.__window, textvariable=self.__buses_count_stringvar, fg=GUI.__GREEN, bg=GUI.__BLACK,
              font=(self.__font_name, 13, "bold"))
        passengers_count_label.place(x=base_x, y=base_y)
        buses_count_label.place(x=base_x + 42, y=base_y + 28)
        #broadcasts
        base_x =self.__server_messages_coords["x"]
        base_y = self.__server_messages_coords["y"]
        jump = self.__server_messages_coords["jump"]
        for i in range(0,Bus.MAX_MESSAGE_COUNT):
            self.__server_broadbast_stringvars_dict[i] = StringVar()
            Label(self.__window, fg=GUI.__GREEN, bg = GUI.__BLACK, font=(self.__font_name, 16, "bold"), textvariable=self.__server_broadbast_stringvars_dict[i]).place(x=base_x, y=base_y+jump*i)
        # statistics
        base_x = self.__statistics_coords["x"]
        base_y = self.__statistics_coords["y"]
        Label(self.__window, text=str(self.__line), fg=GUI.__GREEN, bg = GUI.__BLACK, font=(self.__font_name, 12, "bold")).place(x=base_x, y=base_y)
        Label(self.__window, text=str(self.__id), fg=GUI.__GREEN, bg = GUI.__BLACK, font=(self.__font_name, 12, "bold")).place(x=base_x-14, y=base_y+20)
        Label(self.__window, textvariable=self.__session_time_stringvar, fg=GUI.__GREEN, bg=GUI.__BLACK, font=(self.__font_name, 12, "bold")).place(x=base_x+37, y=base_y+39)

    def __place_free_text_section(self):
        """
        places the free text section
        has a button and an entry that will send messages to the server if needed
        upon a button click the data in the entry will be sent to the server as a message from the bus.
        :return: None
        """

        self.__message_entry = Entry(self.__window, width = 30, borderwidth=0, background = "black", insertbackground ="#1DB954", foreground="#1DB954",font = (self.__font_name, 14))
        self.__send_broadcast_button = Button(self.__window, image=self.__send_btn_img, borderwidth=0, background = "#000000", activebackground = "#083417", command=self.__send_free_text_to_server)
        base_x =self.__broadcast_section_coords["x"]
        base_y =self.__broadcast_section_coords["y"]
        self.__message_entry.place(x=base_x, y=base_y)
        self.__send_broadcast_button.place(x=base_x-3, y=base_y +29)

    def __send_free_text_to_server(self):
        """
        harvests the data from the self.__message_entry, clears the entry
        then tells the bus to send the message to the server
        :return: None
        """

        if self.__bus.connected:
            data = self.__message_entry.get()
            print(f"broad casting data: {data}")
            if not self.__bus.send_free_text(data):
                print("failed to send")
            else:
                self.__message_entry.delete(0, 'end')

        else:
            print("failed to send")

    def __update_table(self):
        """
        recalculates the way the display table is supposed to look and places all the widgets into the table.
        :return: None
        """

        self.__headlines = [str(x) for x in range(1, self.__bus.max_number_of_stations + 1)]
        self.__tree.config(columns=self.__headlines)
        for headline in self.__headlines:
            self.__tree.heading(headline, text=headline)
            self.__tree.column(headline, anchor="center", stretch=False, width=47)
        data = self.__bus.display_passengers()
        for i in self.__tree.get_children():
            self.__tree.delete(i)
        self.__tree.insert("", END, values=data)

    def __update_bg(self):
        """
        changes the background according to the state of the bus
        currently has only 3 states but more states can be easily added
        nobody is waiting - will display a greenish background with the message "nobody is waiting" when there are no passengers waiting
        stop at the next station - will display a red background with the message "somebody is waiting" when there's a passenger at the next station
        lost connection - will display a gray background with the message "lost connection" when the bus loses connection or gets kicked.
        :return: None
        """

        if self.__bus.connected and not self.__bus.kicked:
            if self.__bus.next_station_people_count==0:
                self.__bg_label["image"] = self.__bg_nobody_is_waiting_img
            elif self.__bus.next_station_people_count > 0:
                self.__bg_label["image"] = self.__bg_stop_at_the_next_station_img
        else:
            self.__bg_label["image"] = self.__bg_lost_connection_img


    def display_lost_connection(self):
        """
        creates a window saying that the bus has lost connection to the server
        has a button that says "Reconnect" and will try to reconnect to the server.
        if failed to reconnect a new message will show saying "failed to reestablish connection to the server"
        :return: None
        """

        if self.__bus.stop == True:
            return
        self.__lost_connection_window = Tk()
        self.__lost_connection_popup_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\Lost connection popup.png"),master=self.__lost_connection_window)
        self.__lost_connection_window.geometry(f"{self.__lost_connection_popup_img.width()}x{self.__lost_connection_popup_img.height()}")
        self.__lost_connection_window.iconbitmap(r'Images bus\icon.ico')  # put stuff to icon
        self.__lost_connection_window.title("Lost Connection to the server")
        self.__lost_connection_window.resizable(OFF, OFF)
        self.__bg_label_lost_connection = Label(self.__lost_connection_window, image=self.__lost_connection_popup_img, bg="white")
        self.__bg_label_lost_connection.place(x=0, y=0)
        self.__reconnect_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\reconnect.png"), master=self.__lost_connection_window)
        self.__reconnect_button = tkinter.Button(self.__lost_connection_window, command=lambda: self.__try_to_reconnect("PostLogin"), image=self.__reconnect_img, borderwidth =0, activebackground="white")
        self.__reconnect_button.place(x=152, y=101)
        self.__lost_connection_window.mainloop()
        if not self.__bus.connected:
            sys.exit("closed by user")

    def failed_to_connect(self, firstattempt = True):
        """
        creates a window saying that the bus has failed to establish the first connection to the server.
        has a button that says "Reconnect" and will try to reconnect to the server.
        if failed to reconnect a new message will show saying "failed to reestablish connection to the server"
        :return: None
        """

        if self.__bus.stop == True:
            return
        if not firstattempt:
            self.__failed_to_reconnect_img = ImageTk.PhotoImage(
                PIL.Image.open(r"Images bus\failed to reestablish.png"),
                master=self.__failed_to_connect_window)
            self.__bg_label_failed_to_connect["image"] = self.__failed_to_reconnect_img
            return

        self.__failed_to_connect_window = Tk()
        self.__failed_to_connect_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\failed to establish.png"),
                                                          master=self.__failed_to_connect_window)
        self.__failed_to_connect_window.geometry(
            f"{self.__failed_to_connect_img.width()}x{self.__failed_to_connect_img.height()}")
        self.__failed_to_connect_window.iconbitmap(r'Images bus\icon.ico')  # put stuff to icon
        self.__failed_to_connect_window.title("Failed To Connect")
        self.__failed_to_connect_window.resizable(OFF, OFF)
        self.__bg_label_failed_to_connect = Label(self.__failed_to_connect_window, image=self.__failed_to_connect_img,
                                                  bg="white")
        self.__bg_label_failed_to_connect.place(x=0, y=0)

        self.__reconnect_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\reconnect.png"),
                                                  master=self.__failed_to_connect_window)
        self.__reconnect_button = tkinter.Button(self.__failed_to_connect_window,
                                                 command=lambda: self.__try_to_reconnect("PreLogin"),
                                                 image=self.__reconnect_img, borderwidth=0, activebackground="white")
        self.__reconnect_button.place(x=152, y=101)

        self.__failed_to_connect_window.mainloop()
        if not self.__bus.connected:
            sys.exit("closed by user")

    def display_kicked(self, reason: str):
        """
        creates a window saying that the bus has been kicked from the server
        has a button that says "Reconnect" and will try to reconnect to the server.
        if failed to reconnect a new message will show saying "failed to reestablish connection to the server".
        takes the reason that the bus had been kicked as a parameter,
        currently has no use, but here to make future development easier.
        :param reason: str
        :return: None
        """

        if self.__bus.stop == True:
            return
        self.__kicked_window = Tk()
        self.__kicked_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\kicked.png"),master=self.__kicked_window)
        self.__kicked_window.geometry(f"{self.__kicked_img.width()}x{self.__kicked_img.height()}")
        self.__kicked_window.iconbitmap(r'Images bus\icon.ico')  # put stuff to icon
        self.__kicked_window.title("kicked")
        self.__kicked_window.resizable(OFF, OFF)
        self.__bg_label_kicked = Label(self.__kicked_window, image=self.__kicked_img, bg="white")
        self.__bg_label_kicked.place(x=0, y=0)

        self.__reconnect_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\reconnect.png"), master=self.__kicked_window)
        self.__reconnect_button = tkinter.Button(self.__kicked_window, command=lambda: self.__try_to_reconnect("Kicked"), image=self.__reconnect_img, borderwidth =0, activebackground="white")
        self.__reconnect_button.place(x=152, y=101)
        self.__kicked_window.mainloop()
        if not self.__bus.connected:
            sys.exit("closed by user")

    def display_finished(self):
        """
        opens a window that shows the finished image and all the statistics that come with it.
        shows the session time, and how many people the bus picked up during his ride.
        has an exit button that closes the program and ends the session.
        used as the last window in the program, nothing will open after this window is closed.
        return: None
        """

        self.__window.after_cancel(self.__after_job)
        self.__window.destroy()
        finished_font = ("Bauhaus 93", 30)
        self.__finished_window = Tk()
        self.__finished_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\finished.png"))
        self.__finished_exit_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\exit finished.png"))
        self.__finished_window.geometry(f"{self.__finished_img.width()}x{self.__finished_img.height()}")
        self.__finished_window.iconbitmap(r'Images bus\icon.ico')  # put stuff to icon
        self.__finished_window.title("Finished")
        self.__finished_window.resizable(OFF, OFF)
        bg_label = Label(self.__finished_window, image=self.__finished_img, bg="#1DB954")
        bg_label.place(x=0, y=0)
        self.__people_count_label = Label(self.__finished_window, text=str(self.__bus.total_people_count), bg="#1DB954",
                                          fg="#000000", font=finished_font)
        self.__session_time_label = Label(self.__finished_window, text=str(self.__bus.session_time), fg="#1DB954",
                                          bg="#000000", font=finished_font)
        self.__finish_button = tkinter.Button(self.__finished_window, image=self.__finished_exit_img, command=self.stop,
                                              borderwidth=0, activebackground="gray", fg="red")

        self.__finish_button.place(x=276, y=462)
        self.__people_count_label.place(x=494, y=190)
        self.__session_time_label.place(x=560, y=320)

        self.__finished_window.mainloop()
        if not self.__bus.connected:
            sys.exit("closed by user")

    def __try_to_reconnect(self, status):
        """
        tries to reconnect the bus back to the server
        takes the status of the program when the command was called, can be "PreLogin"\"PostLogin"\"Kicked"
        used in case if failed to reconnect, it makes sure that the correct window will be updated.
        :param status: str
        return: Bool
        """
        if status == "PreLogin":
            if self.__bus.start(first_attempt = False):
                self.__finish_loading_screen(launch_bus=False)
                self.__failed_to_connect_window.destroy()

        elif self.__bus.reconnect():
            if status =="PostLogin":
                self.__lost_connection_window.destroy()
            elif status == "Kicked":
                self.__kicked_window.destroy()
            else:
                print(f"ughh..... i dunno what to do, status: {status} unrecognized")
            self.__bus.asking_user_to_reconnect = False
        else:
            if status == "PostLogin":
                self.__failed_to_reconnect_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\failed to reestablish.png"),
                                                          master=self.__lost_connection_window)
                self.__bg_label_lost_connection["image"]=self.__failed_to_reconnect_img
            elif status == "Kicked":
                self.__failed_to_reconnect_img = ImageTk.PhotoImage(
                    PIL.Image.open(r"Images bus\failed to reestablish.png"),
                    master=self.__kicked_window)
                self.__bg_label_kicked["image"] = self.__failed_to_reconnect_img
            else:
                print(f"ughh..... i dunno what to do, status: {status} unrecognized")

    def config_first_data(self):
        """
        the first thing that the uses sees when he runs the client.
        opens a window asking the user to give some information about the bus he's driving and the line he's working for
        has 3 entries and a finish button
         - id_entry         the bus id
         - line_entry       the line that the bus works for
         - station_entry    the station number that the driver starts from

         - finish_button    passes the entries to the __set_up_data method that takes the data, saves it and closes the window

        :return: None
        """
        window = Tk()
        back_ground_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\opening screen.png"))
        finish_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\finish btn.png"))
        window.geometry(f"{back_ground_img.width()}x{back_ground_img.height()}")
        window.iconbitmap(f'images bus\\icon.ico')  # put stuff to icon
        window.title("User Setup")
        window.resizable(OFF, OFF)
        back_ground_label = Label(window, image=back_ground_img, bg=GUI.__BLACK)
        back_ground_label.place(x=0, y=0)
        station_entry = Entry(window, width=8, borderwidth=0, background = "black", foreground="#1DB954", insertbackground ="#1DB954", font = (self.__font_name, 22))
        station_entry.insert(END, "1")
        station_entry.place(x=570, y=397)
        id_entry = Entry(window, width=20, borderwidth=0, background = "black", foreground="#1DB954", insertbackground ="#1DB954", font = (self.__font_name, 22))
        id_entry.insert(END, str(random.randint(1, 11111111)))
        id_entry.place(x=295, y=247)
        line_entry = Entry(window, width=14, borderwidth=0, background = "black", foreground="#1DB954", insertbackground ="#1DB954", font = (self.__font_name, 22))
        line_entry.insert(END, "14")
        line_entry.place(x=484, y=323)
        finish_button = tkinter.Button(window, image =finish_img, activebackground=GUI.__GREEN, borderwidth=0, background = GUI.__GREEN,
                                       command=lambda: self.__set_up_data(id_entry, station_entry, line_entry, window))
        finish_button.place(x=299, y=478)
        window.mainloop()

    def __set_up_data(self, id_entry, station_entry, line_entry, window):
        """
        checks that all the values given match the expected (all of them are numbers)
        after that stores them as part of the class variables and and closes the given window

        in case if the given values don't match the expectation then a new window will be
        shown saying that the values must be numbers.
        :param id_entry: Entry
        :param station_entry: Entry
        :param line_entry: Entry
        :param window: Tk
        :return: None
        """

        try:
            self.__id = int(id_entry.get())
            self.__line = int(line_entry.get())
            self.__station = int(station_entry.get())
            window.destroy()
        except:
            error_window = Tk()
            error_window.geometry("200x80")
            error_window.iconbitmap(r'Images bus\icon.ico')  # put stuff to icon
            error_window.title("Error")
            error_window.resizable(OFF, OFF)
            error_window.configure(bg="red")
            error_label = Label(error_window, text="Error\n\nValues must be numbers")
            error_label.configure(bg="red")
            error_label.place(x=20, y=20)







def main():
    """
    start the bus client and the gui
    """

    gui = GUI()
    gui.start()


if __name__ == '__main__':
    main()