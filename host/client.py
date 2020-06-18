from time import sleep
from mmeds.spawn import Watcher


def main():
    Watcher.register('get_queue')
    m = Watcher()
    m.connect()
    queue = m.get_queue()
    count = 0
    while True:
        queue.put('{} butt'.format(count))
        count += 1
        sleep(1)


if __name__ == "__main__":
    main()
