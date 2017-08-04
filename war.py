"""
war card game client and server
"""
import asyncio
from collections import namedtuple
from enum import Enum
import logging
import random
import socket
import socketserver
import _thread
import sys

"""
Namedtuples work like classes, but are much more lightweight so they end
up being faster. It would be a good idea to keep objects in each of these
for each game which contain the game's state, for instance things like the
socket, the cards given, the cards still available, etc.
"""
Game = namedtuple("Game", ["p1", "p2"])

class Command(Enum):
    """
    The byte values sent as the first byte of any message in the war protocol.
    """
    WANTGAME = 0
    GAMESTART = 1
    PLAYCARD = 2
    PLAYRESULT = 3

class Result(Enum):
    """
    The byte values sent as the payload byte of a PLAYRESULT message.
    """
    WIN = 0
    DRAW = 1
    LOSE = 2

def readexactly(sock, numbytes):
    """
    Accumulate exactly `numbytes` from `sock` and return those. If EOF is found
    before numbytes have been received, be sure to account for that here or in
    the caller.
    """
    pass

def kill_game(game):
    """
    TODO: If either client sends a bad message, immediately nuke the game.
    """
    game.exit()
    #pass

def compare_cards(card1, card2):
    """
    TODO: Given an integer card representation, return -1 for card1 < card2,
    0 for card1 = card2, and 1 for card1 > card2
    """
    val1 = card1 % 13
    val2 = card2 % 13

    if val1 > val2:
        return 1
    elif val2 > val1:
        return -1
    else:
        return 0

def deal_cards():
    """
    TODO: Randomize a deck of cards (list of ints 0..51), and return two
    26 card "hands."
    """
    deck = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51]
    random.shuffle(deck)
    
    #creating two byte array to send it over network    
    hand1 = bytearray()
    hand1.append(1)
    hand2 = bytearray()
    hand2.append(1)
    index = 0

    for e in deck:
        if index <= 25:
            hand1.append(e)
        else:
            hand2.append(e)
        index = index + 1

    return Game(hand1, hand2)

# One thread will handle multiple clients
def clientThread(c_game):
    hand = deal_cards()

    #receiving first two bytes
    data = c_game.p1.recv(2)
    data = c_game.p2.recv(2)

    #sending two hands
    c_game.p1.send(hand.p1)
    c_game.p2.send(hand.p2)

    index = 1
    # will make multiple calls to clients
    while index <= 26:
        card1 = c_game.p1.recv(2)
        card2 = c_game.p2.recv(2)

        temp = compare_cards(card1[1], card2[1])

        win  = 0
        draw = 1
        lose = 2

        if temp == 1:
            c_game.p1.send(bytes([3,win]))
            c_game.p2.send(bytes([3,lose]))
        if temp == 0:
            c_game.p1.send(bytes([3,draw]))
            c_game.p2.send(bytes([3,draw]))
        if temp == -1:
            c_game.p1.send(bytes([3,lose]))
            c_game.p2.send(bytes([3,win]))
        index =  index + 1

    c_game.p1.close()
    c_game.p2.close()

def serve_game(host, port):
    """
    TODO: Open a socket for listening for new connections on host:port, and
    perform the war protocol to serve a game of war between each client.
    This function should run forever, continually serving clients.
    """
    serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        serverSocket.bind((host,port))
    except:
        print("bind failed")
        sys.exit()

    counter = 0
    serverSocket.listen(1)

    while True:
        conn, addr = serverSocket.accept()
        counter = counter + 1
        if counter == 1:
            p1 = conn
        if counter == 2:
            p2 = conn
            client_game = Game(p1, p2)
            _thread.start_new_thread(clientThread, (client_game,))
            counter = 0
            p1 = ""
            p2 = ""


    serverSocket.close()

async def limit_client(host, port, loop, sem):
    """
    Limit the number of clients currently executing.
    You do not need to change this function.
    """
    async with sem:
        return await client(host, port, loop)

async def client(host, port, loop):
    """
    Run an individual client on a given event loop.
    You do not need to change this function.
    """
    try:
        reader, writer = await asyncio.open_connection(host, port, loop=loop)
        # send want game
        writer.write(b"\0\0")
        card_msg = await reader.readexactly(27)
        myscore = 0
        for card in card_msg[1:]:
            writer.write(bytes([Command.PLAYCARD.value, card]))
            result = await reader.readexactly(2)
            if result[1] == Result.WIN.value:
                myscore += 1
            elif result[1] == Result.LOSE.value:
                myscore -= 1
        if myscore > 0:
            result = "won"
        elif myscore < 0:
            result = "lost"
        else:
            result = "drew"
        logging.debug("Game complete, I %s", result)
        writer.close()
        return 1
    except ConnectionResetError:
        logging.error("ConnectionResetError")
        return 0
    except asyncio.streams.IncompleteReadError:
        logging.error("asyncio.streams.IncompleteReadError")
        return 0
    except OSError:
        logging.error("OSError")
        return 0

def main(args):
    """
    launch a client/server
    """
    host = args[1]
    port = int(args[2])
    if args[0] == "server":
        try:
            # your server should serve clients until the user presses ctrl+c
            serve_game(host, port)
        except KeyboardInterrupt:
            #raise
            pass
        return
    else:
        loop = asyncio.get_event_loop()

    if args[0] == "client":
        loop.run_until_complete(client(host, port, loop))
    elif args[0] == "clients":
        sem = asyncio.Semaphore(1000)
        num_clients = int(args[3])
        clients = [limit_client(host, port, loop, sem)
                   for x in range(num_clients)]
        async def run_all_clients():
            """
            use `as_completed` to spawn all clients simultaneously
            and collect their results in arbitrary order.
            """
            completed_clients = 0
            for client_result in asyncio.as_completed(clients):
                completed_clients += await client_result
            return completed_clients
        res = loop.run_until_complete(
            asyncio.Task(run_all_clients(), loop=loop))
        logging.info("%d completed clients", res)

    loop.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main(sys.argv[1:])