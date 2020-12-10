from mmeds.spawn import Watcher
import coverage; coverage.process_startup()


def main():
    m = Watcher()
    m.start()


if __name__ == "__main__":
    main()
