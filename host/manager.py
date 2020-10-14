from multiprocessing import Process, current_process, Manager, Queue
from time import sleep
from mmeds.spawn import Watcher
import multiprocessing as mp
import multiprocessing.managers as mans
from multiprocessing.managers import BaseManager


def main():
    queue = Queue()
    m = Watcher()
    m.start()
    m.watch()


if __name__ == "__main__":
    main()
