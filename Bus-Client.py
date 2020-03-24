#by Idan Pogrebinsky

#TODO: when the bus is disconnected make the button red and don't let the user hit next.
#TODO: add Next button, and leave
import socket
import threading
import tkinter
from tkinter import *
from tkinter.ttk import Treeview
from time import sleep
import random
import ctypes  # An included library with Python install.


class Bus:
    NEW_CONNECTION_PORT=8200
    STATIONS_PORT=8201
    PASSENGERS_PORT=8202
    HEART_BEAT_PORT=8203
    #HOST = socket.gethostbyname(socket.gethostname())
    HOST = "192.168.3.11" #this client's IP
    ServerIP ="192.168.3.11" # the server's IP
    def __init__(self, gui, id, line_number, station):
        self.__id, self.__line_number, self.__station  = id, line_number, int(station)
        self.__stations = {}
        # stores
        self.__buses = []
        self.asking_user_to_reconnect = False
        self.__gui = gui
        self.stop = False



    def start(self):
        try:
            self.__connect_to_server()
        except:
            self.__gui.failed_to_connect()

        update_tracking_thread = threading.Thread(target=self.__track_updates, args=(), name="updates_tracker")
        update_tracking_thread.start()
        heartbeats_thread = threading.Thread(target=self.__respond_to_heartbeats, args=(), name="heartbeats_thread")
        heartbeats_thread.start()


    def __respond_to_heartbeats(self):
        Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        Socket.bind((self.HOST, self.HEART_BEAT_PORT))
        Socket.listen(1)
        Socket.settimeout(4)
        while not self.stop:
            try:
                client_socket, addr = Socket.accept()
                data = client_socket.recv(1024).decode()
                client_socket.send(str(self.__id).encode())
            except:
                print("we've lost connection to the server")
                self.__connected = False


    def is_connected(self):
        return self.__connected


    def __connect_to_server(self):
        data = f"{self.__line_number} {self.__station} {self.__id}"
        Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        Socket.connect((Bus.ServerIP, Bus.NEW_CONNECTION_PORT))
        Socket.send(data.encode())
        Socket.close()
        self.__connected = True

    def __track_updates(self):
        while not self.stop:
            # establish a connection
            Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            Socket.bind((Bus.HOST, Bus.PASSENGERS_PORT))
            Socket.listen(1)
            client_socket, addr = Socket.accept()
            data = client_socket.recv(1024).decode()
            # data  = {"people"} {station} {number_of_people}
            # data  = {"buses"} {bus1,bus2,bus3....,busn}
            if data.split(" ")[0] == "people":
                type_of_input, station, number_of_people = data.split(" ")
                self.__stations[int(station)] = int(number_of_people)
                print(f"{number_of_people} are waiting at station number {station}, ID:{self.__id}")

            elif data.split(" ")[0] == "buses":
                self.__buses = data.split(" ")[1].split(",")
                map_object = map(int, self.__buses)
                self.__buses = list(map_object)

            Socket.close()

    def next_station(self):
        if self.is_connected():
            try:
                data = f"{self.__line_number} {self.__station+1} {self.__id}"
                self.__send_to_server(data)
                self.__station += 1
            except:
                self.__connected = False
                self.asking_user_to_reconnect = False
        else:
            print("user trying to send update the server about change in the station but i am offline.")

    def __send_to_server(self, data):
        Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        Socket.connect((Bus.ServerIP, Bus.STATIONS_PORT))
        Socket.send(data.encode())
        Socket.close()

    def get_number_of_stations(self):
        #finds how big the table has to be
        # min size = 10
        biggest = max(self.__station, 10)
        if (len(self.__stations) != 0):
            biggest = max(max(self.__stations.keys()), biggest)
        if len(self.__buses)!= 0:
            biggest = max(biggest, max(self.__buses))
        return biggest

    def display_passengers(self):
        list = [""]
        for i in range(self.get_number_of_stations()+1):
            list.append("")

        for station, count in self.__stations.items():
            list[station-1] = str(count)

        for station in self.__buses:
            list[station-1] = "bus"
        list[self.__station-1] = "me"

        return list

    def reconnect(self):
        try:
            self.__connect_to_server()
            self.asking_user_to_reconnect = False
            print("reconnected")
            return True
        except:
            print("failed to reconnect")
            return False



class GUI:
    def __init__(self):
        self.__line, self.__id, self.__station = None, None, None
        self.__bus = None
        self.__headlines = None
        self.config_first_data()
        if self.__line==None:
            sys.exit("Ended by user")

    def start(self):
        self.__bus = Bus(self, self.__id, self.__line, self.__station)
        self.__bus.start()
        self.__headlines = [str(x) for x in range(1, self.__bus.get_number_of_stations() + 1)]
        self.__window = Tk()
        self.__window.geometry("472x150")
        # window.geometry("472x350")
        self.__window.iconbitmap('childhood dream for project.ico')  # put stuff to icon
        self.__window.title("Bus Client")
        self.__window.resizable(OFF, OFF)
        self.__tree = self.__create_table()
        self.__update_Table()
        self.__place_buttons()
        self.__loop()
        self.__window.mainloop()
        self.__bus.stop = True
        sys.exit("closed by user")

    def __create_table(self):
        scrollX = Scrollbar(self.__window, orient=HORIZONTAL)
        tree = Treeview(self.__window, show="headings", columns=self.__headlines, xscrollcommand=scrollX.set)
        scrollX.config(command=tree.xview)
        scrollX.place(x=1, y=81, width=470)
        table_headline_label = Label(self.__window, text="buses and passengers locations")
        table_headline_label.place(x=150, y=0)
        return tree

    def __place_buttons(self):
        self.__next_button = tkinter.Button(self.__window, text="Next Station", command=self.__bus.next_station,
                                     width=25, height=2, activebackground="gray")
        self.__next_button.place(x=50, y=100)

    def __loop(self):
        self.__headlines = [str(x) for x in range(1, self.__bus.get_number_of_stations() + 1)]
        self.__update_Table()
        if not self.__bus.is_connected() and not self.__bus.asking_user_to_reconnect:
            self.__bus.asking_user_to_reconnect = True
            self.__display_disconnected()
        self.__window.after(500, self.__loop)

    def __update_Table(self):
        self.__tree.config(columns=self.__headlines)
        for headline in self.__headlines:
            self.__tree.heading(headline, text=headline)
            self.__tree.column(headline, anchor="center", stretch=False, width=47)

        data = self.__bus.display_passengers()
        for i in self.__tree.get_children():
            self.__tree.delete(i)
        self.__tree.insert("", END, values=data)
        self.__tree.place(x=0, y=30, width=472, height=50)

    def __display_disconnected(self):
        self.__bus.needs_to_reconnect = False
        self.__disconnected_window = Tk()
        self.__disconnected_window.geometry("300x150")
        # window.geometry("472x350")
        self.__disconnected_window.iconbitmap('childhood dream for project.ico')  # put stuff to icon
        self.__disconnected_window.title("Disconnected")
        self.__disconnected_window.resizable(OFF, OFF)
        self.__disconnected_window["bg"] = "red"
        self.__oops_label = Label(self.__disconnected_window, text="oops, looks like we've lose connection.\n"
                                                                   "hit the button to try to fix it")
        self.__oops_label.place(x=50, y=30)
        self.__reconnect_button = tkinter.Button(self.__disconnected_window, text="reconnect",
                                          command=self.__try_to_reconnect,width=30, height=3, activebackground="gray")
        self.__reconnect_button.place(x=50, y=90)

    def __try_to_reconnect(self):
        flag = self.__bus.reconnect()
        print(f"flag = {flag}")
        if flag:
            self.__disconnected_window.destroy()
        else:
            failed_to_connect_label = Label(self.__disconnected_window,
                                            text="sadly i've failed to reconnect, try again in a few seconds")
            failed_to_connect_label.place(x=10, y=10)

    def failed_to_connect(self):
        self.__disconnected_window = Tk()
        self.__disconnected_window.geometry("250x250")
        self.__disconnected_window.iconbitmap('childhood dream for project.ico')  # put stuff to icon
        self.__disconnected_window.title("Error")
        self.__disconnected_window.resizable(OFF, OFF)
        main_label = Label(self.__disconnected_window, text="Failed to connect to the server")
        main_label.place(x=50, y=30)
        next_button = Button(self.__disconnected_window, text="try to reconnect", command=self.__try_to_reconnect, width=10, height=2,
                             activebackground="gray")
        next_button.place(x=160, y=100)
        self.__disconnected_window.mainloop()

    @staticmethod
    def place_entry_and_label(window, text, position, default_value=""):
        print(default_value)
        current_entry = Entry(window, width=20)
        current_entry.insert(END, default_value)
        current_entry.place(x=position[0], y=position[1] + 30)
        current_label = Label(window, text=text)
        current_label.place(x=position[0]+30, y=position[1])
        print(f"placed label :{text}")
        return current_entry

    def config_first_data(self):
        window = Tk()
        window.geometry("350x250")
        window.iconbitmap('childhood dream for project.ico')  # put stuff to icon
        window.title("user setup")
        window.resizable(OFF, OFF)

        main_label = Label(window, text="please enter the needed information about the bus")
        main_label.place(x=50, y=30)

        line_entry = self.place_entry_and_label(window, "Line number", (35, 130),default_value="14")
        id_entry = self.place_entry_and_label(window, "Bus ID", (110, 70),default_value="12345678")
        station_entry = self.place_entry_and_label(window, "station number", (180, 130), default_value="1")
        finish_button = tkinter.Button(window, text="Finish", width=25, height=2, activebackground="gray",
                                       command=lambda: self.set_up_data(id_entry, station_entry, line_entry, window))

        finish_button.place(x=70, y=200)
        window.mainloop()

    def set_up_data(self, id_entry, station_entry, line_entry, window):
        try:
            self.__id = int(id_entry.get())
            self.__line = int(line_entry.get())
            self.__station = int(station_entry.get())
            window.destroy()
        except:
            error_window = Tk()
            error_window.geometry("200x80")
            error_window.iconbitmap('childhood dream for project.ico')  # put stuff to icon
            error_window.title("Error")
            error_window.resizable(OFF, OFF)
            error_window.configure(bg = "red")
            error_label = Label(error_window, text="Error\n\nValues must be real numbers")
            error_label.configure(bg = "red")
            error_label.place(x=20, y=20)




#ID = str(random.randint(1, 999999))
#line_number = 14
#station = 1

gui = GUI()
gui.start()
#
# bus1 = Bus(GUI.ask_basic_data())
# bus1.start()
#
# busGUI = GUI(bus1)
# busGUI.start()




