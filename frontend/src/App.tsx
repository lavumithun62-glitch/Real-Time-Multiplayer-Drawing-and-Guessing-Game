
import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import {
  Alert,
  AppBar,
  Box,
  Button,
  Chip,
  Container,
  Divider,
  Paper,
  Stack,
  TextField,
  Toolbar,
  Typography,
} from '@mui/material';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

type Player = {
  id: number;
  display_name: string;
  score: number;
  ready: boolean;
  connected: boolean;
};

type Room = {
  room_code: string;
  status: string;
  current_round: number;
  total_rounds: number;
  players: Player[];
};

type GameEvent = {
  type: string;
  [key: string]: any;
};

type DrawingOperation = {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  color: string;
  width: number;
  tool: 'brush' | 'eraser';
};

export default function App() {
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [room, setRoom] = useState<Room | null>(null);
  const [playerId, setPlayerId] = useState<number | null>(null);
  const [token, setToken] = useState('');
  const [ready, setReady] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<
    'disconnected' | 'connecting' | 'connected'
  >('disconnected');

  const [word, setWord] = useState('');
  const [drawerId, setDrawerId] = useState<number | null>(null);
  const [seconds, setSeconds] = useState(0);
  const [guess, setGuess] = useState('');
  const [messages, setMessages] = useState<string[]>([]);
  const [notice, setNotice] = useState('');
  const [color, setColor] = useState('#222222');
  const [brush, setBrush] = useState(4);
  const [tool, setTool] = useState<'brush' | 'eraser'>('brush');
  const [busy, setBusy] = useState(false);

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const roomRef = useRef<Room | null>(null);
  const playerIdRef = useRef<number | null>(null);
  const tokenRef = useRef('');
  const credentialsRef = useRef<{
    roomCode: string;
    playerId: number;
    token: string;
  } | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  );
  const reconnectAttemptsRef = useRef(0);
  const intentionalCloseRef = useRef(false);
  const drawingRef = useRef(false);
  const lastPointRef = useRef<{ x: number; y: number } | null>(null);

  roomRef.current = room;
  playerIdRef.current = playerId;
  tokenRef.current = token;

  const addMessage = useCallback((message: string) => {
    setMessages((previous) => [message, ...previous].slice(0, 12));
  }, []);

  const draw = useCallback((operation: DrawingOperation) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const context = canvas.getContext('2d');
    if (!context) return;

    context.lineCap = 'round';
    context.lineJoin = 'round';
    context.strokeStyle =
      operation.tool === 'eraser' ? '#ffffff' : operation.color;
    context.lineWidth = operation.width;

    context.beginPath();
    context.moveTo(
      operation.x0 * canvas.width,
      operation.y0 * canvas.height,
    );
    context.lineTo(
      operation.x1 * canvas.width,
      operation.y1 * canvas.height,
    );
    context.stroke();
  }, []);

  const clearCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const context = canvas.getContext('2d');
    context?.clearRect(0, 0, canvas.width, canvas.height);
  }, []);

  const applyLobby = useCallback((incoming: Room) => {
    setRoom((previous) => {
      const current = previous;

      const mergedPlayers = incoming.players.map((incomingPlayer) => {
        const oldPlayer = current?.players.find(
          (player) => player.id === incomingPlayer.id,
        );

        return {
          ...oldPlayer,
          ...incomingPlayer,
        };
      });

      return {
        ...current,
        ...incoming,
        players: mergedPlayers,
      } as Room;
    });

    const ownId = playerIdRef.current;
    if (ownId !== null) {
      const ownPlayer = incoming.players.find(
        (player) => player.id === ownId,
      );

      if (ownPlayer) {
        setReady(ownPlayer.ready);
      }
    }
  }, []);

  const handleMessage = useCallback(
    (event: GameEvent) => {
      switch (event.type) {
        case 'connection_state':
          if (event.connected) {
            setConnectionStatus('connected');
            reconnectAttemptsRef.current = 0;
            setNotice('');
          } else {
            setConnectionStatus('disconnected');
          }
          break;

        case 'lobby_state':
          applyLobby(event as Room);
          break;

        case 'state_snapshot':
          if (event.status) {
            setRoom((previous) =>
              previous ? { ...previous, status: event.status } : previous,
            );
          }

          if (event.current_round !== undefined) {
            setRoom((previous) =>
              previous
                ? {
                    ...previous,
                    current_round: event.current_round,
                    total_rounds:
                      event.total_rounds ?? previous.total_rounds,
                  }
                : previous,
            );
          }

          if (event.drawer_id !== undefined) {
            setDrawerId(event.drawer_id);
          }

          if (event.seconds_left !== undefined) {
            setSeconds(event.seconds_left);
          }

          if (Array.isArray(event.operations)) {
            clearCanvas();
            event.operations.forEach((operation: DrawingOperation) =>
              draw(operation),
            );
          }

          if (event.word) {
            setWord(event.word);
          }
          break;

        case 'player_joined':
          addMessage(`${event.display_name} joined the room`);
          break;

        case 'player_left':
          addMessage(`${event.display_name} disconnected`);
          break;

        case 'player_ready':
          setRoom((previous) =>
            previous
              ? {
                  ...previous,
                  players: previous.players.map((player) =>
                    player.id === event.player_id
                      ? { ...player, ready: event.ready }
                      : player,
                  ),
                }
              : previous,
          );
          break;

        case 'game_started':
          setRoom((previous) =>
            previous ? { ...previous, status: 'playing' } : previous,
          );
          setNotice('Game started!');
          break;

        case 'round_started':
          setRoom((previous) =>
            previous
              ? {
                  ...previous,
                  status: 'playing',
                  current_round: event.round_number,
                  total_rounds: event.total_rounds,
                }
              : previous,
          );

          setDrawerId(event.drawer_id);
          setWord('');
          setSeconds(event.duration ?? 0);
          clearCanvas();
          setNotice(`Round ${event.round_number} started`);
          break;

        case 'drawer_word':
          setWord(event.word ?? '');
          break;

        case 'timer':
          setSeconds(event.seconds_left ?? 0);
          break;

        case 'stroke':
          if (event.operation) {
            draw(event.operation as DrawingOperation);
          }
          break;

        case 'canvas_cleared':
          clearCanvas();
          break;

        case 'round_ended':
          setNotice(
            event.word
              ? `Round ended. The word was: ${event.word}`
              : 'Round ended',
          );
          setWord('');
          break;

        case 'correct_guess':
          addMessage(
            `${event.display_name} guessed correctly (+${event.points} points)`,
          );
          break;

        case 'scoreboard':
          setRoom((previous) =>
            previous
              ? {
                  ...previous,
                  players: previous.players.map((player) => ({
                    ...player,
                    score:
                      event.scores?.[String(player.id)] ?? player.score,
                  })),
                }
              : previous,
          );
          break;

        case 'guess_result':
        case 'error':
          setNotice(event.message ?? 'An unexpected game event occurred.');
          break;

        case 'game_finished':
          setRoom((previous) =>
            previous ? { ...previous, status: 'completed' } : previous,
          );
          setWord('');
          setNotice(
            'Game finished! ' +
              (event.leaderboard ?? [])
                .map(
                  (player: any) =>
                    `${player.display_name} (${player.score})`,
                )
                .join(', '),
          );
          break;

        default:
          console.debug('Unhandled game event:', event.type);
      }
    },
    [addMessage, applyLobby, clearCanvas, draw],
  );

  const connect = useCallback(
    (roomCode: string, id: number, accessToken: string) => {
      intentionalCloseRef.current = false;

      credentialsRef.current = {
        roomCode,
        playerId: id,
        token: accessToken,
      };

      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }

      const oldSocket = socketRef.current;
      socketRef.current = null;

      if (
        oldSocket &&
        oldSocket.readyState !== WebSocket.CLOSED
      ) {
        oldSocket.close(1000, 'Replacing connection');
      }

      setConnectionStatus('connecting');

      const protocol = API.startsWith('https:') ? 'wss:' : 'ws:';
      const url = new URL(API);

      const socketUrl =
        `${protocol}//${url.host}/ws/` +
        `${encodeURIComponent(roomCode)}/${id}` +
        `?token=${encodeURIComponent(accessToken)}`;

      let socket: WebSocket;

      try {
        socket = new WebSocket(socketUrl);
      } catch (error) {
        console.error('Could not create WebSocket:', error);
        setConnectionStatus('disconnected');
        setNotice('Could not create the game connection.');
        return;
      }

      socketRef.current = socket;

      socket.onopen = () => {
        if (socketRef.current !== socket) return;

        console.info('Game WebSocket opened');
        setConnectionStatus('connected');
        setNotice('');
      };

      socket.onmessage = (messageEvent) => {
        if (socketRef.current !== socket) return;

        try {
          const event: GameEvent = JSON.parse(messageEvent.data);
          handleMessage(event);
        } catch (error) {
          console.error('Invalid WebSocket message:', error);
        }
      };

      socket.onerror = (error) => {
        if (socketRef.current !== socket) return;

        console.error('Game WebSocket error:', error);
        setNotice(
          'Connection error. Check the backend and try reconnecting.',
        );
      };

      socket.onclose = (event) => {
        if (socketRef.current !== socket) return;

        socketRef.current = null;
        setConnectionStatus('disconnected');

        console.warn(
          'Game WebSocket closed:',
          event.code,
          event.reason || '(no reason provided)',
          'clean:',
          event.wasClean,
        );

        if (intentionalCloseRef.current) return;

        setNotice(
          `Connection closed (${event.code}). Attempting to reconnect…`,
        );

        const credentials = credentialsRef.current;
        if (!credentials) return;

        reconnectAttemptsRef.current += 1;

        const delay = Math.min(
          1000 * 2 ** (reconnectAttemptsRef.current - 1),
          10000,
        );

        reconnectTimerRef.current = setTimeout(() => {
          const currentCredentials = credentialsRef.current;

          if (
            !intentionalCloseRef.current &&
            currentCredentials &&
            currentCredentials.roomCode === credentials.roomCode &&
            currentCredentials.playerId === credentials.playerId
          ) {
            connect(
              currentCredentials.roomCode,
              currentCredentials.playerId,
              currentCredentials.token,
            );
          }
        }, delay);
      };
    },
    [handleMessage],
  );

  useEffect(() => {
    return () => {
      intentionalCloseRef.current = true;

      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }

      const socket = socketRef.current;
      socketRef.current = null;

      if (
        socket &&
        socket.readyState !== WebSocket.CLOSED
      ) {
        socket.close(1000, 'Page unmounted');
      }
    };
  }, []);

  function send(data: Record<string, unknown>) {
    const socket = socketRef.current;

    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(data));
    } else {
      setNotice('Not connected yet. Please wait for reconnection.');
    }
  }

  async function createRoom() {
    if (!name.trim() || busy) return;

    setBusy(true);
    setNotice('');

    try {
      const response = await axios.post(`${API}/api/rooms`, {
        display_name: name.trim(),
        total_rounds: 3,
      });

      const data = response.data;

      setCode(data.room_code);
      setPlayerId(data.player_id);
      setToken(data.access_token);
      setRoom(data.room);
      setReady(false);

      playerIdRef.current = data.player_id;
      tokenRef.current = data.access_token;

      connect(data.room_code, data.player_id, data.access_token);
    } catch (error: any) {
      setNotice(
        error.response?.data?.detail ?? 'Could not create the room.',
      );
    } finally {
      setBusy(false);
    }
  }

  async function joinRoom() {
    if (!name.trim() || code.trim().length !== 6 || busy) return;

    setBusy(true);
    setNotice('');

    try {
      const roomCode = code.trim().toUpperCase();

      const response = await axios.post(
        `${API}/api/rooms/${encodeURIComponent(roomCode)}/join`,
        { display_name: name.trim() },
      );

      const data = response.data;

      setCode(data.room_code);
      setPlayerId(data.player_id);
      setToken(data.access_token);
      setRoom(data.room);
      setReady(false);

      playerIdRef.current = data.player_id;
      tokenRef.current = data.access_token;

      connect(data.room_code, data.player_id, data.access_token);
    } catch (error: any) {
      setNotice(
        error.response?.data?.detail ?? 'Could not join the room.',
      );
    } finally {
      setBusy(false);
    }
  }

  function toggleReady() {
    const nextReady = !ready;

    setReady(nextReady);
    send({ type: 'ready', ready: nextReady });
  }

  function getPoint(event: React.PointerEvent<HTMLCanvasElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();

    return {
      x: Math.max(
        0,
        Math.min(1, (event.clientX - bounds.left) / bounds.width),
      ),
      y: Math.max(
        0,
        Math.min(1, (event.clientY - bounds.top) / bounds.height),
      ),
    };
  }

  const isDrawer = playerId === drawerId;

  function startDrawing(event: React.PointerEvent<HTMLCanvasElement>) {
    if (
      !isDrawer ||
      room?.status !== 'playing' ||
      connectionStatus !== 'connected'
    ) {
      return;
    }

    event.currentTarget.setPointerCapture(event.pointerId);
    drawingRef.current = true;
    lastPointRef.current = getPoint(event);
  }

  function continueDrawing(event: React.PointerEvent<HTMLCanvasElement>) {
    if (
      !drawingRef.current ||
      !lastPointRef.current ||
      !isDrawer ||
      connectionStatus !== 'connected'
    ) {
      return;
    }

    const nextPoint = getPoint(event);
    const previousPoint = lastPointRef.current;

    const operation: DrawingOperation = {
      x0: previousPoint.x,
      y0: previousPoint.y,
      x1: nextPoint.x,
      y1: nextPoint.y,
      color,
      width: brush,
      tool,
    };

    draw(operation);
    send({ type: 'stroke', ...operation });
    lastPointRef.current = nextPoint;
  }

  function stopDrawing() {
    drawingRef.current = false;
    lastPointRef.current = null;
  }

  function submitGuess(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!guess.trim()) return;

    send({ type: 'guess', text: guess.trim() });
    setGuess('');
  }

  function leaveRoom() {
    intentionalCloseRef.current = true;
    credentialsRef.current = null;

    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    const socket = socketRef.current;
    socketRef.current = null;

    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'leave' }));
      socket.close(1000, 'Player left');
    } else if (socket) {
      socket.close();
    }

    setRoom(null);
    setPlayerId(null);
    setToken('');
    setReady(false);
    setWord('');
    setDrawerId(null);
    setSeconds(0);
    setMessages([]);
    setConnectionStatus('disconnected');
    setNotice('');
    clearCanvas();
  }

  return (
    <>
      <AppBar position="static">
        <Toolbar>
          <Typography
            variant="h6"
            sx={{ fontWeight: 800, flexGrow: 1 }}
          >
            🎨 Draw &amp; Guess
          </Typography>
          <Typography variant="body2">
            Realtime multiplayer
          </Typography>
        </Toolbar>
      </AppBar>

      <Container maxWidth="lg" sx={{ py: 4 }}>
        {notice && (
          <Alert
            sx={{ mb: 2 }}
            severity={
              connectionStatus === 'disconnected' && room
                ? 'warning'
                : 'info'
            }
            onClose={() => setNotice('')}
          >
            {notice}
          </Alert>
        )}

        {!room ? (
          <Paper sx={{ p: 4, maxWidth: 520, mx: 'auto' }}>
            <Typography variant="h4" fontWeight={800} gutterBottom>
              Play with friends
            </Typography>

            <Typography color="text.secondary" mb={3}>
              Create a room or enter a room code to join a game.
            </Typography>

            <Stack spacing={2}>
              <TextField
                label="Display name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                inputProps={{ maxLength: 40 }}
              />

              <Button
                variant="contained"
                size="large"
                disabled={!name.trim() || busy}
                onClick={createRoom}
              >
                Create room
              </Button>

              <Divider>OR JOIN</Divider>

              <TextField
                label="Room code"
                value={code}
                onChange={(event) =>
                  setCode(event.target.value.toUpperCase())
                }
                inputProps={{ maxLength: 6 }}
              />

              <Button
                variant="outlined"
                size="large"
                disabled={
                  !name.trim() || code.trim().length !== 6 || busy
                }
                onClick={joinRoom}
              >
                Join room
              </Button>
            </Stack>
          </Paper>
        ) : (
          <>
            <Paper sx={{ p: 2, mb: 2 }}>
              <Stack
                direction={{ xs: 'column', sm: 'row' }}
                alignItems={{ sm: 'center' }}
                spacing={2}
              >
                <Box sx={{ flexGrow: 1 }}>
                  <Typography variant="h5" fontWeight={800}>
                    Room {room.room_code}
                  </Typography>

                  <Typography color="text.secondary">
                    {room.status === 'playing'
                      ? `Round ${room.current_round} of ${room.total_rounds}`
                      : room.status === 'completed'
                        ? 'Game completed'
                        : 'Waiting in lobby'}
                  </Typography>
                </Box>

                <Chip
                  label={
                    connectionStatus === 'connected'
                      ? 'Connected'
                      : connectionStatus === 'connecting'
                        ? 'Connecting…'
                        : 'Offline'
                  }
                  color={
                    connectionStatus === 'connected'
                      ? 'success'
                      : 'default'
                  }
                />

                <Button
                  variant="outlined"
                  onClick={() =>
                    navigator.clipboard?.writeText(room.room_code)
                  }
                >
                  Copy room code
                </Button>

                <Chip label={`${room.players.length} players`} />

                {room.status === 'lobby' && (
                  <Button
                    variant="contained"
                    disabled={connectionStatus !== 'connected'}
                    onClick={toggleReady}
                  >
                    {ready ? 'Not ready' : 'Ready'}
                  </Button>
                )}

                {room.status === 'lobby' &&
                  playerId === room.players[0]?.id && (
                    <Button
                      variant="contained"
                      color="success"
                      disabled={connectionStatus !== 'connected'}
                      onClick={() => send({ type: 'start_game' })}
                    >
                      Start game
                    </Button>
                  )}

                <Button color="inherit" onClick={leaveRoom}>
                  Leave
                </Button>
              </Stack>
            </Paper>

            <Box className="game-grid">
              <Paper sx={{ p: 2 }}>
                <Stack
                  direction="row"
                  alignItems="center"
                  spacing={1}
                  mb={2}
                >
                  <Typography
                    variant="h6"
                    fontWeight={800}
                    sx={{ flexGrow: 1 }}
                  >
                    Shared canvas
                  </Typography>

                  <Chip
                    label={
                      isDrawer
                        ? 'You are drawing'
                        : `Drawer: ${
                            room.players.find(
                              (player) => player.id === drawerId,
                            )?.display_name ?? '—'
                          }`
                    }
                  />

                  <Chip label={`${seconds}s`} />
                </Stack>

                {isDrawer && word && (
                  <Alert severity="info" sx={{ mb: 2 }}>
                    Your secret word: <b>{word}</b>
                  </Alert>
                )}

                <canvas
                  ref={canvasRef}
                  width={1000}
                  height={620}
                  className="drawing-canvas"
                  style={{
                    touchAction: 'none',
                    pointerEvents: isDrawer ? 'auto' : 'auto',
                  }}
                  onPointerDown={startDrawing}
                  onPointerMove={continueDrawing}
                  onPointerUp={stopDrawing}
                  onPointerCancel={stopDrawing}
                  onLostPointerCapture={stopDrawing}
                />

                <Stack
                  direction="row"
                  flexWrap="wrap"
                  gap={1}
                  mt={2}
                  alignItems="center"
                >
                  <input
                    aria-label="Brush color"
                    type="color"
                    value={color}
                    onChange={(event) => setColor(event.target.value)}
                  />

                  <TextField
                    size="small"
                    label="Brush size"
                    type="number"
                    value={brush}
                    onChange={(event) =>
                      setBrush(
                        Math.max(
                          1,
                          Math.min(40, Number(event.target.value) || 1),
                        ),
                      )
                    }
                    sx={{ width: 120 }}
                  />

                  <Button
                    variant={tool === 'brush' ? 'contained' : 'outlined'}
                    onClick={() => setTool('brush')}
                  >
                    Brush
                  </Button>

                  <Button
                    variant={tool === 'eraser' ? 'contained' : 'outlined'}
                    onClick={() => setTool('eraser')}
                  >
                    Eraser
                  </Button>

                  <Button
                    color="warning"
                    variant="outlined"
                    disabled={
                      !isDrawer || connectionStatus !== 'connected'
                    }
                    onClick={() => {
                      clearCanvas();
                      send({ type: 'clear_canvas' });
                    }}
                  >
                    Clear canvas
                  </Button>
                </Stack>
              </Paper>

              <Stack spacing={2}>
                <Paper sx={{ p: 2 }}>
                  <Typography variant="h6" fontWeight={800} mb={1}>
                    Scoreboard
                  </Typography>

                  {[...room.players]
                    .sort((a, b) => b.score - a.score)
                    .map((player) => (
                      <Stack
                        key={player.id}
                        direction="row"
                        alignItems="center"
                        spacing={1}
                        py={1}
                      >
                        <Box sx={{ flexGrow: 1 }}>
                          <Typography
                            fontWeight={
                              player.id === playerId ? 700 : 400
                            }
                          >
                            {player.display_name}
                            {player.id === playerId ? ' (you)' : ''}
                          </Typography>

                          <Typography
                            variant="caption"
                            color="text.secondary"
                          >
                            {player.id === drawerId ? 'Drawer · ' : ''}
                            {player.connected ? 'Connected' : 'Offline'}
                          </Typography>
                        </Box>

                        <Typography fontWeight={800}>
                          {player.score}
                        </Typography>
                      </Stack>
                    ))}
                </Paper>

                <Paper sx={{ p: 2 }}>
                  <Typography variant="h6" fontWeight={800} mb={1}>
                    Guess the word
                  </Typography>

                  <Stack
                    component="form"
                    direction="row"
                    spacing={1}
                    onSubmit={submitGuess}
                  >
                    <TextField
                      fullWidth
                      size="small"
                      value={guess}
                      onChange={(event) => setGuess(event.target.value)}
                      placeholder="Type your guess…"
                      disabled={
                        isDrawer ||
                        room.status !== 'playing' ||
                        connectionStatus !== 'connected'
                      }
                    />

                    <Button
                      type="submit"
                      variant="contained"
                      disabled={
                        isDrawer ||
                        room.status !== 'playing' ||
                        connectionStatus !== 'connected' ||
                        !guess.trim()
                      }
                    >
                      Send
                    </Button>
                  </Stack>

                  <Typography
                    variant="caption"
                    color="text.secondary"
                    display="block"
                    mt={1}
                  >
                    The drawer cannot guess. Correct guesses score more
                    points when made quickly.
                  </Typography>
                </Paper>

                <Paper sx={{ p: 2 }}>
                  <Typography variant="h6" fontWeight={800} mb={1}>
                    Players &amp; activity
                  </Typography>

                  {room.players.map((player) => (
                    <Stack
                      key={player.id}
                      direction="row"
                      spacing={1}
                      alignItems="center"
                      py={0.5}
                    >
                      <Chip
                        size="small"
                        label={player.ready ? 'Ready' : 'Not ready'}
                        color={player.ready ? 'success' : 'default'}
                      />

                      <Typography sx={{ flexGrow: 1 }}>
                        {player.display_name}
                      </Typography>

                      <Chip
                        size="small"
                        label={player.connected ? 'Online' : 'Offline'}
                        color={player.connected ? 'success' : 'default'}
                      />
                    </Stack>
                  ))}

                  <Divider sx={{ my: 1 }} />

                  {messages.map((message, index) => (
                    <Typography
                      key={`${index}-${message}`}
                      variant="body2"
                      color="text.secondary"
                    >
                      {message}
                    </Typography>
                  ))}
                </Paper>
              </Stack>
            </Box>
          </>
        )}
      </Container>
    </>
  );
}
