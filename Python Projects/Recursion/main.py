import sys


class Data:
    def __init__(self, data):
        self.value = data

    def __str__(self):
        return str(self.value)


class Node:
    def __init__(self, data, prevNode=None):
        self.data = Data(data)
        self.prevNode = prevNode


class Stack:
    def __init__(self):
        self.head = None

    def isEmpty(self):
        return self.head == None

    def top(self):
        try:
            return self.head.data
        except:
            return None

    def push(self, data):
        if self.head is None:
            self.head = Node(data)
        else:
            new_node = Node(data)
            new_node.prevNode = self.head
            self.head = new_node
        print("\tpush: top - ", str(data))

    def pop(self):
        if self.head is None:
            return None
        else:
            popped = self.head.data
            self.head = self.head.prevNode
            if self.head is not None:
                print("\tpop  - ", str(popped), "\ttop - ", self.head.data)
            else:
                print("\tpop - ", str(popped), "\ttop - Empty")
            return popped

    def empty(self):
        return self.head == None


class StackFrame(Stack):
    def __init__(self):
        Stack.__init__(self)

    def push(self, t):
        Stack.push(self, t)

    def pop(self):
        return Stack.pop(self)

    def top(self):
        return Stack.top(self)

    def empty(self):
        return Stack.empty(self)


frames = StackFrame()


def bitshow(number):
    global frames
    if number > 0:
        frames.push(number)
        bitshow(number >> 1)
        frames.pop()
        if number % 2:
            print('1')
        else:
            print('0')

for i in range(1, 257):
    bitshow(i)