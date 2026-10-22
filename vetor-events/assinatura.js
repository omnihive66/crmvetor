// Vetor Sistemas: autorização das assinaturas do WebSocket (o taiga-events oficial aceita qualquer chave).
//  - changes.project.<id>.*  só se a API do Taiga deixar o usuário ver o projeto (mesmo token);
//  - web_notifications.<id>  só o próprio usuário (o JWT diz quem é);
//  - qualquer outra chave: recusada.
const http = require("http");
const { logger } = require("../logger");
const { getUserId } = require("../crypto");

const API = process.env.TAIGA_BACK_URL || "http://taiga-back:8000";
const PROJETO = /^changes\.project\.(\d+)\.[a-z_.]+$/;
const NOTIFICACOES = /^web_notifications\.(\d+)$/;

const podeVerProjeto = (token, id) => new Promise(resolve => {
  const req = http.get(`${API}/api/v1/projects/${id}`, { headers: { Authorization: `Bearer ${token}` }, timeout: 5000 }, res => {
    res.resume();
    resolve(res.statusCode === 200);
  });
  req.on("timeout", () => req.destroy());
  req.on("error", err => { logger.error(`assinatura: API indisponível (${err.message})`); resolve(false); });
});

const podeAssinar = async (auth, routingKey) => {
  if (!auth || !auth.token) return false;
  let m = NOTIFICACOES.exec(routingKey);
  if (m) return String(getUserId(auth.token)) === m[1];
  m = PROJETO.exec(routingKey);
  if (m) return podeVerProjeto(auth.token, m[1]);
  return false;
};

module.exports = { podeAssinar };
