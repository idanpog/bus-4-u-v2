"""by Idan pogrebinsky"""

import socket
import threading


class Bus:
    """
represents a bus. connects to the main server and keeps up with the new updates coming from the server
    """
    NEW_CONNECTION_PORT = 8200
    STATIONS_PORT = 8201
    PASSENGERS_PORT = 8202
    # HOST = socket.gethostbyname(socket.gethostname())
    HOST = "192.168.3.15"
    ServerIP = "192.168.3.12"

    def __init__(self, line_number, station, ID):
        self.__station = station
        self.__line_number = line_number
        self.__ID = ID
        self.__stations = {}

    def connect_to_server(self):
        """
        connects to the server
        sends the server a message that contains data = {line_number} {station} {ID}"
        closes the socket right after that.
        """
        Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        Socket.connect((Bus.ServerIP, Bus.NEW_CONNECTION_PORT))
        data = f"{self.__line_number} {self.__station} {self.__ID}"
        Socket.send(data.encode())
        Socket.close()

    def update_station(self, station):
        """
        :param station: sends the server the current station
        :return: nothing
        sends a message that looks like data = {line_number} {station} {ID}"
        """
        Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__station = station
        Socket.connect((Bus.ServerIP, Bus.STATIONS_PORT))
        data = f"{self.__line_number} {station} {self.__ID}"
        Socket.send(data.encode())
        Socket.close()

    def start_tracking_people(self):
        """
        launches the people_tracking_thread which keeps track of incoming inputs from the server
        :return: nothing
        """
        people_tracking_thread = threading.Thread(target=self.__track_people, args=(), name="people_tracker")
        people_tracking_thread.start()

    def __track_people(self):
        """
        has an open socket that waits for an incoming connection from the server
        once it gets the information it updates the amount of people waiting
        at the station in the self.__stations dictionary.
        closes the connection and then keeps on waiting for incoming connections
        :return: nothing
        """
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


busID = "bus1"
Line_number = 11
Station = 1
bus1 = Bus(Line_number, Station, busID)
bus1.connect_to_server()
bus1.start_tracking_people()

while True:
    bus1.update_station(input("what station are you at currently"))
