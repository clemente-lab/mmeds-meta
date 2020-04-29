# Comparison of methods of process communication

## Linux socket with TCP/UDP

### Advantages
- Could allow for running jobs and the application on separate servers and communicating over LAN/WAN

### Disadvantages
- Jose says is evil


## IPC Queue

### Advantages
- Most similar to current setup, only using a different library

### Disadvantages
- Jose says is evil

## Shared Memory

### Advantages
- Very fast

### Disadvantages
- Complicated to setup
-


## File System

### Advantages
- Simple initial setup
- Easy to see what is going on

### Disadvantages
- Slow
- Inelegant
- ore likely to encounter race conditions as I'm manually controlling locks
