// Assina chaves do WebSocket como um usuário e lista o que chega em alguns segundos.
// Uso (rede do compose): node eventos.js <token> <segundos> <chave>...
const WebSocket = require("ws");
const [token, segundos, ...chaves] = process.argv.slice(2);
const ws = new WebSocket(process.env.EVENTS_URL || "ws://taiga-events:8888/events");
ws.on("open", () => {
  ws.send(JSON.stringify({ cmd: "auth", data: { token, sessionId: "qa-" + Date.now() } }));
  for (const routing_key of chaves) ws.send(JSON.stringify({ cmd: "subscribe", routing_key }));
  console.log("PRONTO"); setTimeout(() => { ws.close(); process.exit(0); }, segundos * 1000);
});
ws.on("message", m => { const d = JSON.parse(m); if (d.routing_key) console.log("RECEBIDO", d.routing_key); });
