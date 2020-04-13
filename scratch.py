import time



oldtime = time.time()

time.sleep(0.2)

newtime = time.time()
print(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(oldtime)))
print(time.gmtime(0))