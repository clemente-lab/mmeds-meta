from multiprocessing import Process, current_process, Manager, Queue
from time import sleep
from mmeds.spawn import Watcher
import multiprocessing as mp
import multiprocessing.managers as mans
from multiprocessing.managers import BaseManager


class MMEDSManager(BaseManager):
    pass

def main2():
    m = mans.MMEDSManager(address=("", 50000), authkey=b'butts')
    m.start()
    q = m.Queue()
    while True:
        print(q.get())
        sleep(3)

    print(q)


def main():
    queue = Queue()
    # Watcher.register('get_queue', callable=lambda: queue)
    m = Watcher()
    m.start()
    m.watch()
    #m.set_queue()
    #m.print_queue()
    #queue = m.get_queue()
    #while True:
    #    print(queue.get())
    #    sleep(1)




if __name__ == "__main__":
    main()
