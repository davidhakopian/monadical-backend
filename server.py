import websockets
import asyncio
import json
import mysql.connector

class Game:
    id = None
    player1 = None
    player2 = None
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

def create1PlayerGame(websocket):
    print("New 1 Player game created")
    newGame = Game()
    newGame.player1 = websocket
    newGame.player2 = "AI"
    sql = "INSERT INTO games (player1Address) VALUES (%s)"
    remoteAddress = str(websocket.remote_address[0]) + ":" + str(websocket.remote_address[1])
    dbcursor.execute(sql, (remoteAddress,))
    DB.commit()
    newGame.id = dbcursor.lastrowid
    print("Current game id: " + str(newGame.id))
    GAMES.append(newGame)   
    return newGame  

def create2PlayerGame(websocket):
    ##If there are no games or all games are full, create new one
    if len(GAMES) == 0 or GAMES[len(GAMES)-1].player2 is not None:
        print("New game created")
        newGame = Game()
        newGame.player1 = websocket
        sql = "INSERT INTO games (player1Address) VALUES (%s)"
        remoteAddress = str(websocket.remote_address[0]) + ":" + str(websocket.remote_address[1])
        dbcursor.execute(sql, (remoteAddress,))
        DB.commit()
        newGame.id = dbcursor.lastrowid
        print("Current game id: " + str(newGame.id))
        GAMES.append(newGame)   
        return newGame  
    ##If game exists with only one player, join the game
    else:
        print("Player 2 joined game")
        currentGame = GAMES[len(GAMES)-1]
        currentGame.player2 = websocket
        sql = "UPDATE games set player2Address = %s WHERE id = %s"
        remoteAddress = str(websocket.remote_address[0]) + ":" + str(websocket.remote_address[1])
        dbcursor.execute(sql, (remoteAddress, currentGame.id))
        DB.commit()
        return currentGame

def getGameIdList():
    sql = "SELECT * from games"
    dbcursor.execute(sql)
    result = dbcursor.fetchall()
    return(list(map(getGameId, result)))

def getGameId(gameTuple): 
    return gameTuple[0]

def getMoveList(gameId):
    sql = "SELECT * from moves WHERE gameId = %s ORDER BY turnNumber ASC"
    dbcursor.execute(sql, (gameId,))
    result = dbcursor.fetchall()
    return(list(map(getMoveObject, result)))

def getMoveObject(moveTuple):
    return {
        "x": moveTuple[3],
        "y": moveTuple[4]
    }

def saveMove(x, y, game):      
    sql = "INSERT INTO moves (gameId, turnNumber, x, y) VALUES (%s, %s, %s, %s)"
    dbcursor.execute(sql, (game.id, game.turnsPlayed, x, y))
    DB.commit()

async def listen(websocket, path):
    try:
        currentGame = None
        print("A player just joined")
        
        async for message in websocket:
            jsonData = json.loads(message)
            print("Recieved message of type: " + str(jsonData["type"]))
            
            if jsonData["type"] == "newGame1P":
                currentGame = create1PlayerGame(websocket)
                await currentGame.player1.send(json.dumps({
                        "type": "newGame",
                        "youStart": 1
                    }))    
            elif jsonData["type"] == "newGame2P":
                currentGame = create2PlayerGame(websocket)
                if currentGame.player2 != None:
                    await currentGame.player1.send(json.dumps({
                        "type": "newGame",
                        "youStart": 1
                    }))
                    await currentGame.player2.send(json.dumps({
                        "type": "newGame",
                        "youStart": 0
                    }))
            elif jsonData["type"] == "getGameList":    
                sendList = {
                    "type": "gameList",
                    "list": getGameIdList(),
                }
                await websocket.send(json.dumps(sendList))
            elif jsonData["type"] == "getMoveList":
                sendList = {
                    "type": "moveList",
                    "list": getMoveList(jsonData["gameId"]),
                }
                await websocket.send(json.dumps(sendList))
            elif jsonData["type"] == "move":
                currentGame.turnsPlayed = currentGame.turnsPlayed + 1
                saveMove(jsonData["x"], jsonData["y"], currentGame) 
                if currentGame.player2 != "AI":
                    moveToSend = {
                        "type": "move",
                        "x": jsonData["x"],
                        "y": jsonData["y"]
                    } 
                    if currentGame.player1 == websocket:
                        await currentGame.player2.send(json.dumps(moveToSend))
                    else:
                        await currentGame.player1.send(json.dumps(moveToSend))

    except websockets.exceptions.ConnectionClosed as e:
        print("A player just disconnected, " + str(e))


start_server = websockets.serve(listen, 'localhost', PORT)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()