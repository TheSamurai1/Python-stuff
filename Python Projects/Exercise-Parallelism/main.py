import threading
import time
import multiprocessing

def f(i):
    for p in range(3):
        time.sleep(i + 1)
        print('Thread #', i, "\n")
        time.sleep(i)
    return


# start threads by passing function to Thread constructor
if __name__  == '__main__':
    for i in range(3):

        t = multiprocessing.Process(target = f, args = (i,))
        t.start()

