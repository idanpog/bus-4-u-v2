# by Idan Pogrebinsky

import random
import socket
import threading
import tkinter
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

class Bus:
    NEW_CONNECTION_PORT = 8200
    STATIONS_PORT = 8201
    PASSENGERS_PORT = 8202
    HEART_BEAT_PORT = 8203
    HOST = socket.gethostbyname(socket.gethostname())
    MAX_STATION = 14
    PULSE_DELAY = 5
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
        biggest = max(self.__station, 10)
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
                if time.time() -self.__connection_established_time < Bus.PULSE_DELAY+1:
                    print("connection is too young, skipping this heartbeat")
                else:
                    if self.__connected == True and not self.__kicked:
                        print("lost connection to the server")
                        self.__connected = False
                        self.__gui.display_disconnected()
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
        print(f"driver recieved a message{chunk}")
        for message in chunk.split(","):
            self.__server_free_text_messages.append({"text":message, "time": time.time()})
        if len(self.__server_free_text_messages) > 3:
            self.__server_free_text_messages = self.__server_free_text_messages[-5::]

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
    def __init__(self):
        self.__line, self.__id, self.__station = None, None, None
        self.__bus = None
        self.__headlines = None
        self.config_first_data()
        self.asking_to_reconnect = False
        self.__passengers_count_stringvar = None
        self.__buses_count_stringvar =None
        self.__server_broadbast_stringvar = None
        self.__session_time_stringvar = None

        if self.__line == None:
            sys.exit("Ended by user")

    def start(self):
        self.__bus = Bus(self, self.__id, self.__line, self.__station)
        self.__bus.start()
        self.__headlines = [str(x) for x in range(1, self.__bus.max_number_of_stations + 1)]
        self.__window = Tk()
        self.__window.geometry("472x700")
        # window.geometry("472x350")
        self.__window.iconbitmap(f'images bus\\childhood dream for project.ico')  # put stuff to icon
        self.__window.title("Bus Client")
        self.__window.resizable(OFF, OFF)
        self.__passengers_count_stringvar = StringVar()
        self.__buses_count_stringvar =StringVar()
        self.__server_broadbast_stringvar = StringVar()
        self.__session_time_stringvar = StringVar()
        self.__tree = self.__create_table()
        self.__place_titles()
        self.__update_table()
        self.__place_buttons()
        self.__place_labels()
        self.__place_free_text_section()
        self.__update_image()
        self.__loop()

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

    def __create_table(self):
        scrollX = Scrollbar(self.__window, orient=HORIZONTAL)
        tree = Treeview(self.__window, show="headings", columns=self.__headlines, xscrollcommand=scrollX.set)
        scrollX.config(command=tree.xview)
        scrollX.place(x=1, y=81, width=470)
        #table_headline_label = Label(self.__window, text="buses and passengers locations")
        #table_headline_label.place(x=150, y=0)

        return tree

    def __place_buttons(self):
        self.__next_button = tkinter.Button(self.__window, text="Next Station", command=self.__bus.next_station,
                                            width=25, height=2, activebackground="gray")
        self.__next_button.place(x=50, y=100)

        self.__stop_button = tkinter.Button(self.__window, text="exit", command=self.stop,
                                            width=10, height=2, activebackground="gray", fg="red")
        self.__stop_button.place(x=380, y=100)

    def __update_labels(self):
        self.__passengers_count_stringvar.set("Number of people waiting: " + str(self.__bus.count_people()))
        self.__buses_count_stringvar.set("Number of buses working for the same line: " + str(self.__bus.count_buses()))
        self.__session_time_stringvar.set(f"Session time: {self.__bus.session_time}")
        server_broadbast_text = ""
        for message in self.__bus.server_free_text_messages:
            if time.time() - message["time"] > 10:

                print(f"message was too old, removed: {time.strftime('%H:%M:%S', time.localtime(message['time']))}: {message['text']} \n")
                self.__bus.server_free_text_messages.remove(message)
            server_broadbast_text +=f"{time.strftime('%H:%M:%S', time.localtime(message['time']))}: {message['text']} \n"

        if len(server_broadbast_text)>0:
            server_broadbast_text = server_broadbast_text[:-1:]
        self.__server_broadbast_stringvar.set(server_broadbast_text)

    def __loop(self):
        if self.__bus.stop == True:
            return
        try:
            self.__headlines = [str(x) for x in range(1, self.__bus.max_number_of_stations + 1)]
            self.__update_table()
            self.__update_image()
            self.__update_labels()
            #self.__update_server_broadcasts()
            self.__after_job = self.__window.after(500, self.__loop)
        except Exception as e:
            print(f"Done looping because: {e}")

    def __place_labels(self):
        # statistics labels
        self.__passengers_count_stringvar.set("Number of people waiting: " + str(self.__bus.count_people()))
        self.__buses_count_stringvar.set("Number of buses working for the same line: " + str(self.__bus.count_buses()))
        self.__server_broadbast_stringvar.set("Empty")

        Label(self.__window, textvariable=self.__passengers_count_stringvar).place(x=10, y=650)
        Label(self.__window, textvariable=self.__buses_count_stringvar).place(x=10, y=670)
        Label(self.__window, textvariable=self.__server_broadbast_stringvar).place(x=30, y=350)

        # labels about myself
        line_label = Label(self.__window, text="my line: " + str(self.__line), fg="gray")
        line_label.place(x=350, y=530)
        id_label = Label(self.__window, text="my ID: " + str(self.__id), fg="gray")
        id_label.place(x=350, y=550)
        session_time_label = Label(self.__window, textvariable=self.__session_time_stringvar, fg="gray")
        session_time_label.place(x=350, y=570)

    def __place_free_text_section(self):
        self.__message_label = Label(self.__window, text = "Send important messages to the admins")
        self.__message_entry = Entry(self.__window, width = 53)
        self.__message_to_server_button = Button(self.__window,height=2, width = 22, text="Send message to server",command= self.__send_free_text_to_server)

        self.__message_label.place(x=100, y=510)
        self.__message_entry.place(x=20, y=535)
        self.__message_to_server_button.place(x=100, y=555)

        print("placed broadcast section")

    def __send_free_text_to_server(self):
        data = self.__message_entry.get()

        self.__message_entry.delete(0, 'end')
        print(f"broad casting data: {data}")
        self.__bus.send_free_text(data)

    def __place_titles(self):
        display_live_updates = Label(self.__window, text="Live buses and the passengers locations")
        server_broadcasts = Label(self.__window, text="Server Broad Casts ")
        statistics_label = Label(self.__window, text="Statistics ")
        display_live_updates.place(x = 150, y= 10)
        server_broadcasts.place(x = 180, y = 320)
        statistics_label.place(x = 220, y = 600)

    def __update_table(self):
        self.__tree.config(columns=self.__headlines)
        for headline in self.__headlines:
            self.__tree.heading(headline, text=headline)
            self.__tree.column(headline, anchor="center", stretch=False, width=47)

        data = self.__bus.display_passengers()
        for i in self.__tree.get_children():
            self.__tree.delete(i)
        self.__tree.insert("", END, values=data)
        self.__tree.place(x=0, y=30, width=472, height=50)

    def __update_image(self):
        if self.__bus.next_station_people_count==0:
            self.img_go = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\nobody is waiting.png"))
            self.go_label = Label(self.__window, image=self.img_go)
            self.go_label.place(x=0, y= 160)
        else:
            self.img_stop = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\stop at the next station-idan.png"))
            self.go_label = Label(self.__window, image=self.img_stop)
            self.go_label.place(x=0, y=160)

        #.pack(side="bottom", fill="both", expand="yes")

    def display_disconnected(self):
        # a display that pops when the bus loses connection
        if self.__bus.stop == True:
            return
        self.__window["bg"] = "gray"
        self.__disconnected_window = Tk()
        self.__disconnected_window.geometry("300x150")
        self.__disconnected_window.iconbitmap(r'Images bus\childhood dream for project.ico')  # put stuff to icon
        self.__disconnected_window.title("Disconnected")
        self.__disconnected_window.resizable(OFF, OFF)
        self.__disconnected_window["bg"] = "red"
        self.__oops_label = Label(self.__disconnected_window, text="oops, looks like we've lose connection.\n"
                                                                   "hit the button to try to fix it", bg="red")
        self.__oops_label.place(x=30, y=30)
        self.__reconnect_button = tkinter.Button(self.__disconnected_window, text="ReConnect",
                                                 command=lambda: self.__try_to_reconnect("PostLogin"), width=28,
                                                 height=3, activebackground="gray")
        self.__reconnect_button.place(x=50, y=90)
        self.__disconnected_window.mainloop()
        if not self.__bus.connected:
            sys.exit("closed by user")

    def display_kicked(self, reason: str):
        # a display that pops when the bus loses connection
        if self.__bus.stop == True:
            return
        self.__window["bg"] = "gray"
        self.__kicked_window = Tk()
        self.__kicked_window.geometry("500x150")
        self.__kicked_window.iconbitmap(r'Images\childhood dream for project.ico')  # put stuff to icon
        self.__kicked_window.title("kicked")
        self.__kicked_window.resizable(OFF, OFF)
        self.__kicked_window["bg"] = "yellow"
        self.__oops_label = Label(self.__kicked_window, text=f"looks like you've been kicked for reason: {reason}\n"
                                                                   "hit the button to try to reconnect", bg="yellow")
        self.__oops_label.place(x=30, y=30)
        self.__reconnect_button = tkinter.Button(self.__kicked_window, text="ReConnect",
                                                 command=lambda: self.__try_to_reconnect("Kicked"), width=28,
                                                 height=3, activebackground="gray")
        self.__reconnect_button.place(x=50, y=90)
        self.__kicked_window.mainloop()
        if not self.__bus.connected:
            sys.exit("closed by user")

    def display_finished(self):
        self.__window.after_cancel(self.__after_job)
        self.__window.destroy()

        self.__finished_window = Tk()
        self.__finished_window.geometry("300x250")
        self.__finished_window.iconbitmap(r'Images\childhood dream for project.ico')  # put stuff to icon
        self.__finished_window.title("Finished")
        self.__finished_window.resizable(OFF, OFF)
        self.__finished_window["bg"] = "White"
        self.__finished_label = Label(self.__finished_window, text="you've finished your route for today", fg="blue")
        self.__people_count_label = Label(self.__finished_window,
                                          text=f"You've transported today {self.__bus.total_people_count} people to their targets")
        self.__session_time_label = Label(self.__finished_window,
                                          text=f"Your session time was {self.__bus.session_time}")
        self.__finish_button = tkinter.Button(self.__finished_window, text="finish", command=self.stop,
                                              width=10, height=2, activebackground="gray", fg="red")

        self.__finish_button.place(x=50, y=90)
        self.__finished_label.place(x=30, y=30)
        self.__people_count_label.place(x=10, y=130)
        self.__session_time_label.place(x=10, y=150)

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
            if status == "PostLogin" or status == "Kicked":
                self.__window["bg"] = 'SystemButtonFace'#sets the window color back to normal after reconnecting
            else:
                print(f"not changing back the color, the status is {status}")
            if status =="PostLogin" or status == "PreLogin":
                self.__disconnected_window.destroy()
            else:
                self.__kicked_window.destroy()
            self.__bus.asking_user_to_reconnect = False

        else:
            failed_to_connect_label = Label(self.__disconnected_window,
                                            text="sadly i've failed to reconnect  \n try again in a few seconds")
            if status == "PostLogin":
                failed_to_connect_label.place(x=10, y=10)
            elif status == "PreLogin":
                failed_to_connect_label.place(x=43, y=25)

    def failed_to_connect(self):
        # a display that pops when the bus fails to establish the first connection
        self.__disconnected_window = Tk()
        self.__disconnected_window.geometry("250x150")
        self.__disconnected_window.iconbitmap(r'Images\childhood dream for project.ico')  # put stuff to icon
        self.__disconnected_window.title("Error")
        self.__disconnected_window.resizable(OFF, OFF)
        main_label = Label(self.__disconnected_window, text="Failed to connect to the server")
        main_label.place(x=40, y=30)
        reconnect_button = Button(self.__disconnected_window, text="try to reconnect", height=3, width=25
                                  , activebackground="gray", command=lambda: self.__try_to_reconnect("PreLogin"))
        reconnect_button.place(x=32, y=90)
        self.__disconnected_window.mainloop()
        try:
            print(self.__bus.connected)
        except:
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
        window.geometry("350x250")
        window.iconbitmap(f'images bus\\childhood dream for project.ico')  # put stuff to icon
        window.title("user setup")
        window.resizable(OFF, OFF)

        main_label = Label(window, text="please enter the needed information about the bus")
        main_label.place(x=50, y=30)

        line_entry = self.place_entry_and_label(window, "Line number", (35, 130), default_value="14")
        id_entry = self.place_entry_and_label(window, "Bus ID", (110, 70),
                                              default_value=str(random.randint(1, 11111111)))
        station_entry = self.place_entry_and_label(window, "station number", (180, 130), default_value="1")
        finish_button = tkinter.Button(window, text="Finish", width=25, height=2, activebackground="gray",
                                       command=lambda: self.__set_up_data(id_entry, station_entry, line_entry, window))

        finish_button.place(x=70, y=200)
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

