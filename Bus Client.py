#by Idan Pogrebinsky

import socket
import threading


class Bus:
    NEW_CONNECTION_PORT=8200
    STATIONS_PORT=8201
    PASSENGERS_PORT=8202
    #HOST = socket.gethostbyname(socket.gethostname())
    HOST = "192.168.3.15"
    ServerIP ="192.168.3.12"
    def __init__(self, line_number, station, ID):
        self.__station = station
        self.__line_number = line_number
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
            self.__stations[station] = number_of_people
            Socket.close()
            print(f"{number_of_people} are waiting at station number {station}, ID:{self.__ID}")




ID = "bus1"
line_number = 11
station = 1
bus1 = Bus(line_number, station, ID)
bus1.connect_to_server()
bus1.start_tracking_people()

while True:
    bus1.update_station(input("what station are you at currently"))





