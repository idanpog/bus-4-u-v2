#by Idan Pogrebinsky

import socket
import threading
from tkinter import *
from tkinter.ttk import Treeview
from time import sleep

class Bus:
    NEW_CONNECTION_PORT=8200
    STATIONS_PORT=8201
    PASSENGERS_PORT=8202
    #HOST = socket.gethostbyname(socket.gethostname())
    HOST = "192.168.56.1" #this client's IP
    ServerIP ="192.168.56.1" # the server's IP
    def __init__(self, line_number, station, ID):
        self.__station = int(station)
        self.__line_number = int(line_number)
        self.__ID = ID
        self.__stations = {}

    def connect_to_server(self):
        Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        Socket.connect((Bus.ServerIP, Bus.NEW_CONNECTION_PORT))
        data = f"{self.__line_number} {self.__station} {self.__ID}"
        Socket.send(data.encode())
        Socket.close()

    def update_station(self, station):
        Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__station = station
        Socket.connect((Bus.ServerIP, Bus.STATIONS_PORT))
        data = f"{self.__line_number} {station} {self.__ID}"
        Socket.send(data.encode())
        Socket.close()

    def start_tracking_people(self):
        people_tracking_thread = threading.Thread(target=self.__track_people, args=(), name="people_tracker")
        people_tracking_thread.start()

    def __track_people(self):
        while True:
            # establish a connection
            Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            Socket.bind((Bus.HOST, Bus.PASSENGERS_PORT))
            Socket.listen(1)
            client_socket, addr = Socket.accept()
            print("print getting an update from the server")
            data = client_socket.recv(1024)
            # data  = {station} {number_of_people}
            station, number_of_people = data.decode().split(" ")
            self.__stations[int(station)] = int(number_of_people)
            Socket.close()
            print(f"{number_of_people} are waiting at station number {station}, ID:{self.__ID}")

    def get_number_of_stations(self):
        if (len(self.__stations) == 0):
            return max(station,10)
        return max(station, max(self.__stations.keys()), 10)

    def display_passengers(self):
        list = [""]
        for i in range(self.get_number_of_stations()+1):
            list.append("")

        for station, count in self.__stations.items():
            list[station-1] = str(count)

        list[self.__station-1] = "x"

        return list

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


def update_labels(tree, window, bus_controller):
    #active_lines_label = Label(window, text="Number of active lines: " + str(len(bus_controller.get_bus_dict())))
    #number_of_buses_label = Label(window, text="Number of buses in the system: " + str(bus_controller.countbuses()))
    #number_of_people_lable = Label(window, text="Number of people waiting: " + str(bus_controller.countpeople()))

    #active_lines_label.place(x=500, y=0)
    #number_of_buses_label.place(x=500, y=30)
    #number_of_people_lable.place(x=500, y=60)
    pass

def launch_GUI(bus):
    window = Tk()
    window.geometry("472x150")
    window.iconbitmap('childhood dream for project.ico')  # put stuff to icon
    window.title("my stations")
    window.resizable(OFF, OFF)
    tree = table(bus, window)
    update(tree, window, bus)
    window.mainloop()


ID = "bus1"
line_number = 14
station = 5
bus1 = Bus(line_number, station, ID)
bus1.connect_to_server()
bus1.start_tracking_people()

launch_GUI(bus1)
while True:
    bus1.update_station(input("what station are you at currently"))





