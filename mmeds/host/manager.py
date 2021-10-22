from mmeds.spawn import Watcher
import coverage

# I don't think this even helps but I tried
coverage.process_startup()


def main():
    m = Watcher()
    m.start()


if __name__ == "__main__":
    main()
