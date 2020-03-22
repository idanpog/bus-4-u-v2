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
    def __init__(self, line_number, station, ID):
        self.__station = int(station)
        self.__line_number = int(line_number)
        self.__ID = ID
        self.__stations = {}
        # stores
        self.__buses = []
        self.asking_user_to_reconnect = False


    def start(self):
        self.__connect_to_server()
        update_tracking_thread = threading.Thread(target=self.__track_updates, args=(), name="updates_tracker")
        update_tracking_thread.start()
        heartbeats_thread = threading.Thread(target=self.__respond_to_heartbeats, args=(), name="heartbeats_thread")
        heartbeats_thread.start()

    def __respond_to_heartbeats(self):
        Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        Socket.bind((self.HOST, self.HEART_BEAT_PORT))
        Socket.listen(1)
        Socket.settimeout(11)
        while True:
            try:
                client_socket, addr = Socket.accept()
                data = client_socket.recv(1024).decode()
                print(data)
                client_socket.send(str(self.__ID).encode())
            except:
                print("we've lost connection to the server")
                self.__connected = False


    def is_connected(self):
        return self.__connected


    def __connect_to_server(self):
        data = f"{self.__line_number} {self.__station} {self.__ID}"
        Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        Socket.connect((Bus.ServerIP, Bus.NEW_CONNECTION_PORT))
        Socket.send(data.encode())
        Socket.close()
        self.__connected = True

    def __track_updates(self):
        while True:
            # establish a connection
            Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            Socket.bind((Bus.HOST, Bus.PASSENGERS_PORT))
            Socket.listen(1)
            client_socket, addr = Socket.accept()
            data = client_socket.recv(1024).decode()
            # data  = {"people"} {station} {number_of_people}
            # data  = {"buses"} {bus1,bus2,bus3....,busn}
            print(data)
            if data.split(" ")[0] == "people":
                type_of_input, station, number_of_people = data.split(" ")
                self.__stations[int(station)] = int(number_of_people)
                print(f"{number_of_people} are waiting at station number {station}, ID:{self.__ID}")

            elif data.split(" ")[0] == "buses":
                self.__buses = data.split(" ")[1].split(",")
                map_object = map(int, self.__buses)
                self.__buses = list(map_object)
                print(f"edited self.__buses, looks like {self.__buses}")

            Socket.close()

    def next_station(self):
        if self.is_connected():
            try:
                data = f"{self.__line_number} {self.__station+1} {self.__ID}"
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
        print(f"in display passengers and it looks like {self.__buses}")
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
        print("hey")
        try:
            self.__connect_to_server()
            self.asking_user_to_reconnect = False
            return True
        except:
            print("failed to recconect")
            return False



def table(bus, window):
    headlines= list(range(1, bus.get_number_of_stations()+1))
    scrollX = Scrollbar(window, orient=HORIZONTAL)
    tree = Treeview(window, show="headings", columns=headlines, xscrollcommand=scrollX.set)
    scrollX.config(command=tree.xview)
    scrollX.place(x=1, y=81, width=470)
    table_headline_label = Label(window, text="buses and passengers locations")
    table_headline_label.place(x=150, y=0)
    return tree


def update(tree, window, bus):
    update_Table(tree, window, bus)
    update_labels(tree, window, bus)
    if not bus.is_connected() and not bus.asking_user_to_reconnect:
        bus.asking_user_to_reconnect = True
        display_disconnected(bus)
    window.after(2000, update, tree, window, bus)


def update_Table(tree, window, bus):

    headlines= list(range(1, bus.get_number_of_stations()+1))

    tree.config(columns=headlines)
    for headline in headlines:
        tree.heading(headline, text=headline)
        tree.column(headline, anchor="center",stretch= False, width = 47)

    data = bus.display_passengers()
    for i in tree.get_children():
        tree.delete(i)
    tree.insert("", END, values=data)
    tree.place(x=0, y=30, width=472, height=50)


def display_disconnected(bus):
    bus.needs_to_reconnect = False
    disconnected_window = Tk()
    disconnected_window.geometry("300x150")
    # window.geometry("472x350")
    disconnected_window.iconbitmap('childhood dream for project.ico')  # put stuff to icon
    disconnected_window.title("Disconnected")
    disconnected_window.resizable(OFF, OFF)
    disconnected_window["bg"] = "red"
    oops_label = Label(disconnected_window, text="oops, looks like we've lose connection.\nhit the button"
                                                           " to try to fix it")
    oops_label.place(x=50, y=30)
    reconnect_button = tkinter.Button(disconnected_window, text="reconnect", command=lambda: try_to_reconnect(bus, disconnected_window)
                                      , width=30, height=3,activebackground="gray")
    reconnect_button.place(x=50, y=90)

def try_to_reconnect(bus, disconnect_window):
    flag = bus.reconnect()
    print(f"flag = {flag}")
    if flag:
        print("reconnected, and now destroying window")
        disconnect_window.destroy()
    else:
        print("somehow im here")
        failed_to_connect_label = Label(disconnect_window, text="sadly i've failed to reconnect, try again in a few seconds")
        failed_to_connect_label.place(x=10, y=10)

def update_labels(tree, window, bus_controller):
    #active_lines_label = Label(window, text="Number of active lines: " + str(len(bus_controller.get_bus_dict())))
    #number_of_buses_label = Label(window, text="Number of buses in the system: " + str(bus_controller.countbuses()))
    #number_of_people_lable = Label(window, text="Number of people waiting: " + str(bus_controller.countpeople()))

    #active_lines_label.place(x=500, y=0)
    #number_of_buses_label.place(x=500, y=30)
    #number_of_people_lable.place(x=500, y=60)
    pass


def place_buttons(tree, window, bus):
    next_button = tkinter.Button(window, text="Next Station", command=bus.next_station, width = 25, height= 2,
                                 activebackground = "gray")
    next_button.place(x = 50, y = 100)


def launch_GUI(bus):
    window = Tk()
    window.geometry("472x150")
    #window.geometry("472x350")
    window.iconbitmap('childhood dream for project.ico')  # put stuff to icon
    window.title("my stations")
    window.resizable(OFF, OFF)
    tree = table(bus, window)
    place_buttons(tree, window, bus)
    update(tree, window, bus)
    window.mainloop()

ID = str(random.randint(1,999999))
line_number = 14
station = 1
bus1 = Bus(line_number, station, ID)
bus1.start()

launch_GUI(bus1)




