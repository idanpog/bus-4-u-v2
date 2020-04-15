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

font_name= "Bahnschrift SemiBold SemiConden"
kicked_window = Tk()
kicked_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\kicked.png"))
reconnect_img = ImageTk.PhotoImage(PIL.Image.open(r"Images bus\reconnect.png"))
bg_label = Label(kicked_window, image=kicked_img, bg="white")
bg_label.place(x=0, y=0)
kicked_window.geometry(f"{kicked_img.width()}x{kicked_img.height()}")
kicked_window.iconbitmap(r'Images bus\childhood dream for project.ico')  # put stuff to icon
kicked_window.title("Finished")
kicked_window.resizable(OFF, OFF)
finish_button = tkinter.Button(kicked_window, image= reconnect_img, borderwidth =0, activebackground="white")
finish_button.place(x=152, y=101)


kicked_window.mainloop()