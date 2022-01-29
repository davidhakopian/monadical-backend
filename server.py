import websockets
import asyncio
import json
import mysql.connector

class Game:
    id = None
    player1 = None
    player2 = None
    playerTurn = 1
    turnsPlayed = 0

DB = mysql.connector.connect(
    host = "localhost",
    user = "root",
    database = "monadical_db"
)

dbcursor = DB.cursor(buffered=True)

dbcursor.execute("SHOW TABLES")
for x in dbcursor:
    print(x)

try:   
    dbcursor.execute("CREATE TABLE IF NOT EXISTS games (id INT PRIMARY KEY AUTO_INCREMENT, player1Address VARCHAR(255), player2Address VARCHAR(255))")
except Exception as e:
    print(str(e))
    
try:   
    dbcursor.execute("CREATE TABLE IF NOT EXISTS moves (id INT PRIMARY KEY AUTO_INCREMENT, gameId INT, turnNumber INT, x INT, y INT, FOREIGN KEY (gameId) REFERENCES games(id))")
except Exception as e:
    print(str(e))

PORT = 8765

GAMES = []

print("Listening on port: " + str(PORT))

async def listen(websocket, path):
    try:
        print(str(path))
        currentGame = None
        currentPlayer = None
        
        print("A player just joined")
        ##If there are no games or all games are full, create new one
        if len(GAMES) == 0 or GAMES[len(GAMES)-1].player2 is not None:
            print("New game created")
            currentGame = Game()
            currentGame.player1 = websocket
            sql = "INSERT INTO games (player1Address) VALUES (%s)"
            remoteAddress = str(websocket.remote_address[0]) + ":" + str(websocket.remote_address[1])
            dbcursor.execute(sql, (remoteAddress,))
            DB.commit()
            currentGame.id = dbcursor.lastrowid
            print("Current game id: " + str(currentGame.id))
            currentPlayer = 1
            GAMES.append(currentGame)
            setup = {
                "type": "setup",
                "player": 1,
            }
            await websocket.send(json.dumps(setup))
            
        ##If game exists with only one player, join the game
        else:
            print("Player 2 joined game")
            currentGame = GAMES[len(GAMES)-1]
            currentPlayer = 2
            currentGame.player2 = websocket
            sql = "UPDATE games set player2Address = %s WHERE id = %s"
            remoteAddress = str(websocket.remote_address[0]) + ":" + str(websocket.remote_address[1])
            dbcursor.execute(sql, (remoteAddress, currentGame.id))
            DB.commit()
            setup = {
                "type": "setup",
                "player": 2,
            }
            await websocket.send(json.dumps(setup))
            ##Alert both players that game is ready to begin
            startGameMessage = {
                "type": "startGame"
            }
            await currentGame.player1.send(json.dumps(startGameMessage))
            await currentGame.player2.send(json.dumps(startGameMessage))
    
    
        async for message in websocket:
            print("Recieved message from player: " + str(currentPlayer))
            jsonData = json.loads(message)
            
            move = {
                "type": "move",
                "x": jsonData["x"],
                "y": jsonData["y"]
            }
            
            currentGame.turnsPlayed = currentGame.turnsPlayed + 1
            
            sql = "INSERT INTO moves (gameId, turnNumber, x, y) VALUES (%s, %s, %s, %s)"
            dbcursor.execute(sql, (currentGame.id, currentGame.turnsPlayed, jsonData["x"], jsonData["y"]))
            DB.commit()
            
            if(currentPlayer == 1):
                await currentGame.player2.send(json.dumps(move))
            else:
                await currentGame.player1.send(json.dumps(move))
            
    except websockets.exceptions.ConnectionClosed as e:
        print("A player just disconnected, " + str(e))

start_server = websockets.serve(listen, 'localhost', PORT)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()