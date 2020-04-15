# by Idan Pogrebinsky

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


# TODO: add custom fonts and better looking icons
# TODO: add some better formating at the finish display so if the bus session time was above a minute it'll display everything
# TODO: add a display that will show the bus if he needs to stop or not, make it change colors
# TODO: add buses chat
# TODO: fix all the access modifiers
# TODO: move buttons
# TODO: make the server broadcasts display something even when empty
# TODO: make the buttons update on they're own (make use of dat fresh StringVar())
# TODO: check why it shows 0 buses working in the same line while the bus itself is working.
# TODO: don't let the user hit send when the bus is offline

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
        self.__data_handler = {"buses": self.__proccess_buses_chunk,
                               "passengers": self.__proccess_passengers_chunk,
                               "free text": self.__proccess_free_text_chunk,
                               "kicked for reason": self.__proccess_kick_chunk}
        self.__server_free_text_messages = list(dict()) #{"text": str(), "time": time.time()}
        self.__connection_established_time = None


    @property
    def connected(self):
        return self.__connected
    @property
    def kicked(self):
        return self.__kicked
    @property
    def total_people_count(self):
        return self.__total_people_count

    @property
    def session_time(self):
        session_time = int(time.time() - self.__starting_time)
        local_time = time.gmtime(session_time)
        return time.strftime('%H:%M:%S', local_time)
        #return output

    @property
    def next_station_people_count(self):
        if int(self.__station+1) in self.__stations.keys():
            return self.__stations[self.__station+1]

        return 0

    @property
    def server_free_text_messages(self):
        return self.__server_free_text_messages
    @property
    def max_number_of_stations(self):
        min_number_of_stations = 16
        biggest = max(self.__station, min_number_of_stations)
        if (len(self.__stations) != 0):
            biggest = max(max(self.__stations.keys()), biggest)
        if len(self.__buses) != 0:
            biggest = max(biggest, max(self.__buses))
        return biggest

    def start(self):
        try:
            self.__connect_to_server()
        except:
            self.__gui.failed_to_connect()
        self.__starting_time = time.time()
        update_tracking_thread = threading.Thread(target=self.__track_updates, args=(), name="updates_tracker")
        update_tracking_thread.start()
        heartbeats_thread = threading.Thread(target=self.__respond_to_heartbeats, args=(), name="heartbeats_thread")
        heartbeats_thread.start()

    def __respond_to_heartbeats(self):
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

        chunks = chunk.split(",")

        int_chunks = map(int, chunks) #converts the data from str to int
        self.__buses = list(int_chunks)#makes sure that the data is a list
        self.__buses.remove(self.__station) #removes the bus itself from his own display


    def __proccess_passengers_chunk(self, chunk:str):
        """one of the 3 mini functions that are used to process data received from the server"""
        self.__stations = {}
        if len(chunk) == 0:
            return

        for station in chunk.split(","):
            station_number, people_count = station.split("-")
            self.__stations[int(station_number)] = int(people_count)

    def __proccess_free_text_chunk(self, chunk:str):
        for message in chunk.split(","):
            self.__server_free_text_messages.append({"text":message, "time": time.time()})
        if len(self.__server_free_text_messages) > Bus.MAX_MESSAGE_COUNT:
            self.__server_free_text_messages = self.__server_free_text_messages[-Bus.MAX_MESSAGE_COUNT::]

    def __proccess_kick_chunk(self, chunk:str):
        print("in kick")
        self.__kicked = True
        self.__gui.display_kicked(chunk)

    def next_station(self):

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
        data = f"{self.__line_number} {self.__station} {self.__id}"
        data +=f" message:{free_text}"
        self.__send_to_server(data)

    def __send_to_server(self, data):
        Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        Socket.connect((Bus.ServerIP, Bus.STATIONS_PORT))
        Socket.send(data.encode())
        Socket.close()

    def display_passengers(self):
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
        try:
            self.__connect_to_server()
            print("reconnected")
            return True
        except:
            print("failed to reconnect")
            return False

    def count_people(self):
        return sum(self.__stations.values())

    def count_buses(self):
        total = 0
        for bus in self.__buses:
            total += 1
        return total


class GUI:
    __PATH_TO_IMAGES = 'Images\\'
    __BLACK = "#000000"
    __GREEN = "#105e29"
    __GREEN1 = "#1DB954"

    def __init__(self):
        self.__line, self.__id, self.__station = None, None, None
        self.__bus = None
        self.__font_name = "Bahnschrift SemiBold SemiConden"
        self.__headlines = None
        self.asking_to_reconnect = False
        self.__passengers_count_stringvar = None
        self.__buses_count_stringvar = None
        self.__session_time_stringvar = None
        self.__server_broadbast_stringvars_dict = dict()
        self.__statistics_coords = {"x": 540, "y": 408}
        self.__updating_statistics_coords ={"x": 680, "y": 331}
        self.__next_btn_coords = {"x": 29, "y": 177}
        self.__exit_btn_coords = {"x": 29, "y": 490}
        self.__broadcast_section_coords = {"x": 44, "y": 427}
        self.__server_messages_coords =  {"x": 66, "y": 326, "jump": 36}
        self.__table_coords = {"x": 26, "y": 74, "width" : 744, "height":59}


    def start(self):
        self.config_first_data()
        if self.__line == None:
            sys.exit("Ended by user")
        self.__bus = Bus(self, self.__id, self.__line, self.__station)
        self.__bus.start()
        self.__headlines = [str(x) for x in range(1, self.__bus.max_number_of_stations + 1)]
        self.__window = Tk()


        # window.geometry("472x350")
        self.__window.iconbitmap(f'images bus\\childhood dream for project.ico')  # put stuff to icon
        self.__window.title("Bus Client")
        self.__window.resizable(OFF, OFF)
        self.__start_loading_screen()
        self.__window.mainloop()
        self.stop()

    def stop(self):
        print("in STOP")
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
        loading_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\loading screen.png"))
        self.__window.geometry(f"{loading_img.width()}x{loading_img.height()}")
        self.__bg_label = Label(self.__window, image=loading_img, bg="#192b3d")
        self.__bg_label.place(x=0, y=0)

        self.__window.after(10, self.__finish_loading_screen)
        self.__window.mainloop()

    def __finish_loading_screen(self):
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


        self.__create_table()
        self.__update_table()
        self.__place_buttons()
        self.__place_labels()
        self.__place_free_text_section()

        self.__window.geometry(f"{self.__bg_nobody_is_waiting_img.width()}x{self.__bg_nobody_is_waiting_img.height()}")
        self.__update_bg()

        self.__loop()

    def __loading_screen(self):
        loading_window = Tk()
        loading_window.geometry("740x740")
        loading_window.title("Loading")
        loading_window.resizable(OFF, OFF)
        loading_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\loading screen.png"))
        loading_label = Label(loading_window, image=loading_img, bg ="#192b3d")
        loading_label.place(x=0, y=0)
        loading_window.after(1000, lambda: loading_window.destroy())
        loading_window.mainloop()

    def __create_table(self):
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
        self.__next_button = tkinter.Button(self.__window, image=self.__next_btn_img, command=self.__bus.next_station, borderwidth=0, background = "#000000", activebackground = "#083417")
        self.__next_button.place(x=self.__next_btn_coords["x"], y=self.__next_btn_coords["y"])
        self.__exit_button = tkinter.Button(self.__window, command=self.stop, image=self.__exit_btn_img, borderwidth=0, background = GUI.__BLACK, activebackground = GUI.__BLACK, fg="red")
        self.__exit_button.place(x=self.__exit_btn_coords["x"], y=self.__exit_btn_coords["y"])

    def __update_labels(self):
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

        while len(messages) <Bus.MAX_MESSAGE_COUNT:
            messages.append("")

        for i in range(0,Bus.MAX_MESSAGE_COUNT):
            self.__server_broadbast_stringvars_dict[i].set(messages[i])

    def __loop(self):
        if self.__bus.stop == True:
            return
        try:
            self.__headlines = [str(x) for x in range(1, self.__bus.max_number_of_stations + 1)]
            self.__update_table()
            self.__update_bg()
            self.__update_labels()
            #self.__update_server_broadcasts()
            self.__after_job = self.__window.after(500, self.__loop)
        except Exception as e:
            print(f"Done looping because: {e}")

    def __place_labels(self):
        # statistics labels
        self.__passengers_count_stringvar.set(str(self.__bus.count_people()))
        self.__buses_count_stringvar.set(str(self.__bus.count_buses()))
#        self.__server_broadbast_stringvar.set("")
        #changing statistics
        base_x = self.__updating_statistics_coords["x"]
        base_y = self.__updating_statistics_coords["y"]
        Label(self.__window, textvariable=self.__passengers_count_stringvar,fg=GUI.__GREEN,bg = GUI.__BLACK, font=(self.__font_name, 13, "bold")).place(x=base_x, y=base_y)
        Label(self.__window, textvariable=self.__buses_count_stringvar,fg=GUI.__GREEN,bg = GUI.__BLACK, font=(self.__font_name, 13, "bold")).place(x=base_x+42, y=base_y+28)
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
        self.__message_entry = Entry(self.__window, width = 30, borderwidth=0, background = "black", insertbackground ="#1DB954", foreground="#1DB954",font = (self.__font_name, 14))
        self.__send_broadcast_button = Button(self.__window, image=self.__send_btn_img, borderwidth=0, background = "#000000", activebackground = "#083417", command=self.__send_free_text_to_server)
        base_x =self.__broadcast_section_coords["x"]
        base_y =self.__broadcast_section_coords["y"]
        self.__message_entry.place(x=base_x, y=base_y)
        self.__send_broadcast_button.place(x=base_x-3, y=base_y +29)

        print("placed broadcast section")

    def __send_free_text_to_server(self):
        data = self.__message_entry.get()
        self.__message_entry.delete(0, 'end')
        print(f"broad casting data: {data}")
        self.__bus.send_free_text(data)

    def __update_table(self):
        self.__tree.config(columns=self.__headlines)
        for headline in self.__headlines:
            self.__tree.heading(headline, text=headline)
            self.__tree.column(headline, anchor="center", stretch=False, width=47)
        data = self.__bus.display_passengers()
        for i in self.__tree.get_children():
            self.__tree.delete(i)
        self.__tree.insert("", END, values=data)

    def __update_bg(self):
        if self.__bus.connected and not self.__bus.kicked:
            if self.__bus.next_station_people_count==0:
                self.__bg_label["image"] = self.__bg_nobody_is_waiting_img
            elif self.__bus.next_station_people_count > 0:
                self.__bg_label["image"] = self.__bg_stop_at_the_next_station_img
        else:
            self.__bg_label["image"] = self.__bg_lost_connection_img


    def display_lost_connection(self):
        # a display that pops when the bus loses connection
        if self.__bus.stop == True:
            return
        self.__lost_connection_window = Tk()
        self.__lost_connection_popup_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\Lost connection popup.png"),master=self.__lost_connection_window)
        self.__lost_connection_window.geometry(f"{self.__lost_connection_popup_img.width()}x{self.__lost_connection_popup_img.height()}")
        self.__lost_connection_window.iconbitmap(r'Images bus\childhood dream for project.ico')  # put stuff to icon
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

    def display_kicked(self, reason: str):
        # a display that pops when the bus loses connection
        if self.__bus.stop == True:
            return
        self.__kicked_window = Tk()
        self.__kicked_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\kicked.png"),master=self.__kicked_window)
        self.__kicked_window.geometry(f"{self.__kicked_img.width()}x{self.__kicked_img.height()}")
        self.__kicked_window.iconbitmap(r'Images bus\childhood dream for project.ico')  # put stuff to icon
        self.__kicked_window.title("kicked")
        self.__kicked_window.resizable(OFF, OFF)
        self.__bg_label_kicked = Label(self.__kicked_window, image=self.__kicked_img, bg="white")
        self.__bg_label_kicked.place(x=0, y=0)

        self.__reconnect_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\reconnect.png"), master=self.__kicked_window)
        print("about to sup")
        self.__reconnect_button = tkinter.Button(self.__kicked_window, command=lambda: self.__try_to_reconnect("Kicked"), image=self.__reconnect_img, borderwidth =0, activebackground="white")
        print("sup")
        self.__reconnect_button.place(x=152, y=101)
        self.__kicked_window.mainloop()
        if not self.__bus.connected:
            sys.exit("closed by user")

    def display_finished(self):
        self.__window.after_cancel(self.__after_job)
        self.__window.destroy()
        finished_font = ("Bauhaus 93", 30)
        self.__finished_window = Tk()
        self.__finished_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\finished.png"))
        self.__finished_exit_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\exit finished.png"))
        self.__finished_window.geometry(f"{self.__finished_img.width()}x{self.__finished_img.height()}")
        self.__finished_window.iconbitmap(r'Images bus\childhood dream for project.ico')  # put stuff to icon
        self.__finished_window.title("Finished")
        self.__finished_window.resizable(OFF, OFF)
        self.__finished_window.iconbitmap(r'Images bus\childhood dream for project.ico')  # put stuff to icon
        self.__finished_window.title("Finished")
        self.__finished_window.resizable(OFF, OFF)
        bg_label = Label(self.__finished_window, image=self.__finished_img, bg="#1DB954")
        bg_label.place(x=0, y=0)
        self.__people_count_label = Label(self.__finished_window, text=str(self.__bus.total_people_count),  bg="#1DB954", fg = "#000000", font = ("Bauhaus 93", 30))
        self.__session_time_label = Label(self.__finished_window, text=str(self.__bus.session_time),  fg="#1DB954", bg = "#000000", font = ("Bauhaus 93", 30))
        self.__finish_button = tkinter.Button(self.__finished_window, image = self.__finished_exit_img, command=self.stop, borderwidth =0, activebackground="gray", fg="red")

        self.__finish_button.place(x=276, y=462)
        self.__people_count_label.place(x=494, y=190)
        self.__session_time_label.place(x=560, y=320)
        self.__finished_window.mainloop()


        # TODO: add statistics
        # TODO: add an image
        self.__finished_window.mainloop()
        if not self.__bus.connected:
            sys.exit("closed by user")

    def __try_to_reconnect(self, status):
        # the function that the button "reconnect" calls when pressed.
        # tries to reconnect the bus to the server, notfies the user if failed

        # status = PreLogin\PostLogin\Kicked
        if self.__bus.reconnect():
            if status =="PostLogin":
                self.__lost_connection_window.destroy()
            elif status == "PreLogin":
                self.__failed_to_connect_window.destroy()
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
            elif status == "PreLogin":
                self.__failed_to_reconnect_img = ImageTk.PhotoImage(
                    PIL.Image.open(r"Images bus\failed to reestablish.png"),
                    master=self.__failed_to_connect_window)
                self.__bg_label_failed_to_connect["image"] = self.__failed_to_reconnect_img
            elif status == "Kicked":
                self.__failed_to_reconnect_img = ImageTk.PhotoImage(
                    PIL.Image.open(r"Images bus\failed to reestablish.png"),
                    master=self.__kicked_window)
                self.__bg_label_kicked["image"] = self.__failed_to_reconnect_img
            else:
                print(f"ughh..... i dunno what to do, status: {status} unrecognized")

    def failed_to_connect(self):
        # a display that pops when the bus fails to establish the first connection
        if self.__bus.stop == True:
            return
        self.__failed_to_connect_window = Tk()
        self.__failed_to_connect_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\failed to establish.png"),master=self.__failed_to_connect_window)
        self.__failed_to_connect_window.geometry(f"{self.__failed_to_connect_img.width()}x{self.__failed_to_connect_img.height()}")
        self.__failed_to_connect_window.iconbitmap(r'Images bus\childhood dream for project.ico')  # put stuff to icon
        self.__failed_to_connect_window.title("Failed To Connect")
        self.__failed_to_connect_window.resizable(OFF, OFF)
        self.__bg_label_failed_to_connect = Label(self.__failed_to_connect_window, image=self.__failed_to_connect_img, bg="white")
        self.__bg_label_failed_to_connect.place(x=0, y=0)

        self.__reconnect_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\reconnect.png"), master=self.__failed_to_connect_window)
        self.__reconnect_button = tkinter.Button(self.__failed_to_connect_window, command=lambda: self.__try_to_reconnect("PreLogin"), image=self.__reconnect_img, borderwidth =0, activebackground="white")
        self.__reconnect_button.place(x=152, y=101)

        self.__failed_to_connect_window.mainloop()
        if not self.__bus.connected:
            sys.exit("closed by user")


    @staticmethod
    def place_entry_and_label(window, text, position, default_value=""):
        print(default_value)
        current_entry = Entry(window, width=20)
        current_entry.insert(END, default_value)
        current_entry.place(x=position[0], y=position[1] + 30)
        current_label = Label(window, text=text)
        current_label.place(x=position[0] + 30, y=position[1])
        return current_entry

    def config_first_data(self):
        window = Tk()
        back_ground_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\opening screen.png"))
        finish_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\finish btn.png"))
        window.geometry(f"{back_ground_img.width()}x{back_ground_img.height()}")
        window.iconbitmap(f'images bus\\childhood dream for project.ico')  # put stuff to icon
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
        try:
            self.__id = int(id_entry.get())
            self.__line = int(line_entry.get())
            self.__station = int(station_entry.get())
            window.destroy()


        except:
            error_window = Tk()
            error_window.geometry("200x80")
            error_window.iconbitmap(r'Images\childhood dream for project.ico')  # put stuff to icon
            error_window.title("Error")
            error_window.resizable(OFF, OFF)
            error_window.configure(bg="red")
            error_label = Label(error_window, text="Error\n\nValues must be real numbers")
            error_label.configure(bg="red")
            error_label.place(x=20, y=20)




gui = GUI()
gui.start()