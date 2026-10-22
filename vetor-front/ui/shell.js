/* Barra lateral global + utilitários das telas da Vetor (window.Vetor). Sem dependências.
   No app do Taiga só a barra é usada; as telas próprias usam também Vetor.api/el/estado. */
(function () {
  "use strict";
  var script = document.currentScript;
  var RAIZ = new URL("../../", script.src).pathname;            // /vetor/ui/shell.js -> raiz do site
  var SPRITE = RAIZ + (script.getAttribute("data-sprite") || ""); // sprite do Taiga (pasta versionada, posta pelo build)
  var AUTH = /^(login|forgot-password|change-password|register|invitation|cancel-account|verify-email|change-email|external-apps)/;
  var api = null, me = null;

  function token() { try { return JSON.parse(localStorage.getItem("token")); } catch (e) { return null; } }
  function icone(id) { return '<svg aria-hidden="true"><use href="' + SPRITE + "#" + id + '"></use></svg>'; }
  function rota() { return location.pathname.slice(RAIZ.length); }

  function endereçoApi() {
    if (api) return Promise.resolve(api);
    // Sempre o conf.json: o window.taigaConfig do app começa com valores padrão até carregá-lo.
    return fetch(RAIZ + "conf.json").then(function (r) { return r.json(); }).then(function (c) { return (api = c.api.replace(/\/$/, "")); });
  }

  function chamar(caminho, opcoes) {
    opcoes = opcoes || {};
    return endereçoApi().then(function (base) {
      var headers = Object.assign({ "Accept-Language": "pt-br", Authorization: "Bearer " + token() }, opcoes.headers || {});
      if (!(opcoes.body instanceof FormData)) headers["Content-Type"] = "application/json";
      return fetch(base + caminho, Object.assign({}, opcoes, { headers: headers }));
    }).then(function (r) {
      return (r.status === 204 ? Promise.resolve(null) : r.json().catch(function () { return null; })).then(function (corpo) {
        if (!r.ok) {
          var msg = corpo && (corpo._error_message || (typeof corpo === "object" && Object.values(corpo).flat().join(" "))) || "Erro " + r.status;
          throw Object.assign(new Error(msg), { status: r.status, corpo: corpo });
        }
        return { corpo: corpo, total: Number(r.headers.get("x-pagination-count") || 0), proxima: !!r.headers.get("x-pagination-next") };
      });
    });
  }

  function itens() {
    var lista = [
      ["", "Visão geral", "icon-dashboard", /^$/],
      ["vetor/clientes/", "Clientes", "icon-briefcase", /^vetor\/clientes\//],
      ["projects/", "Projetos", "icon-folder", /^(projects|project)\//],
    ];
    if (me && me.administrador) lista.push(["vetor/administracao/", "Administração", "icon-settings", /^vetor\/administracao\//]);
    return lista;
  }

  function desenhar() {
    var aside = document.querySelector(".vt-shell");
    var visivel = token() && !AUTH.test(rota());
    document.documentElement.classList.toggle("vt-shell-on", !!visivel);
    if (!visivel) { if (aside) aside.hidden = true; return; }
    if (!aside) {
      aside = document.createElement("aside");
      aside.className = "vt-shell"; aside.id = "vt-shell"; aside.setAttribute("aria-label", "Navegação principal");
      document.body.prepend(aside);
      var abrir = document.createElement("button");
      abrir.className = "vt-shell-abrir"; abrir.type = "button"; abrir.setAttribute("aria-controls", "vt-shell");
      abrir.setAttribute("aria-expanded", "false"); abrir.setAttribute("aria-label", "Abrir menu");
      abrir.innerHTML = icone("icon-list");
      var fundo = document.createElement("div"); fundo.className = "vt-shell-fundo";
      document.body.prepend(fundo); document.body.prepend(abrir);
      abrir.onclick = function () { alternarGaveta(true); };
      fundo.onclick = function () { alternarGaveta(false); };
      document.addEventListener("keydown", function (e) { if (e.key === "Escape") alternarGaveta(false); });
    }
    aside.hidden = false;
    var atual = rota();
    aside.innerHTML =
      '<a class="vt-shell-marca" href="' + RAIZ + '" title="Visão geral" target="_self"><img src="' + RAIZ + 'vetor/logo-vetor-original.jpg" alt="Vetor Sistemas" width="640" height="640"></a>' +
      '<form class="vt-shell-busca" role="search" action="' + RAIZ + 'vetor/busca/">' + icone("icon-search") +
      '<input type="search" name="q" minlength="2" placeholder="Buscar clientes, projetos…" aria-label="Busca global"></form>' +
      "<nav>" + itens().map(function (i) {
        // target=_self: no app do Taiga o roteador do AngularJS capturaria o clique em telas que não são dele.
        return '<a href="' + RAIZ + i[0] + '"' + (i[0].indexOf("vetor/") === 0 ? ' target="_self"' : "") +
          (i[3].test(atual) ? ' aria-current="page"' : "") + ' title="' + i[1] + '">' + icone(i[2]) + "<span>" + i[1] + "</span></a>";
      }).join("") + "</nav>" +
      '<button class="vt-shell-recolher" type="button" aria-pressed="' + recolhido() + '">' +
      icone(recolhido() ? "icon-arrow-right" : "icon-arrow-left") + "<span>" + (recolhido() ? "Expandir menu" : "Recolher menu") + "</span></button>";
    aside.querySelector(".vt-shell-recolher").onclick = function () {
      try { localStorage.setItem("vetor-shell-recolhido", recolhido() ? "0" : "1"); } catch (e) {}
      aplicarRecolhido(); desenhar();
    };
    // O app do Taiga troca de rota sem recarregar: links internos fecham a gaveta no celular.
    aside.querySelectorAll("nav a").forEach(function (a) { a.addEventListener("click", function () { alternarGaveta(false); }); });
  }

  function recolhido() { try { return localStorage.getItem("vetor-shell-recolhido") === "1"; } catch (e) { return false; } }
  function aplicarRecolhido() { document.documentElement.classList.toggle("vt-shell-recolhido", recolhido()); }
  function alternarGaveta(abrir) {
    document.documentElement.classList.toggle("vt-shell-aberto", abrir);
    var b = document.querySelector(".vt-shell-abrir");
    if (b) b.setAttribute("aria-expanded", String(abrir));
    if (abrir) { var campo = document.querySelector(".vt-shell input"); if (campo) campo.focus(); }
  }

  function carregarMe() {
    var t = token();
    if (!t) { me = null; return Promise.resolve(); }
    return chamar("/vetor/perfis/me").then(function (r) { me = r.corpo; }, function () { me = null; });
  }

  // Reage a login/logout e às trocas de rota do app do Taiga (pushState) sem depender dele.
  var ultimo = null;
  function sincronizar() {
    var chave = token() + "|" + location.pathname;
    if (chave === ultimo) return;
    var tokenMudou = !ultimo || ultimo.split("|")[0] !== String(token());
    ultimo = chave;
    (tokenMudou ? carregarMe() : Promise.resolve()).then(desenhar);
  }
  aplicarRecolhido();
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", sincronizar); else sincronizar();
  setInterval(sincronizar, 1000);

  function el(tag, attrs) {
    var e = document.createElement(tag);
    Object.entries(attrs || {}).forEach(function (kv) {
      if (kv[1] === null || kv[1] === undefined || kv[1] === false) return;
      if (kv[0] === "text") e.textContent = kv[1];
      else if (kv[0].slice(0, 2) === "on") e[kv[0]] = kv[1];
      else e.setAttribute(kv[0], kv[1] === true ? "" : kv[1]);
    });
    for (var i = 2; i < arguments.length; i++) if (arguments[i] !== null && arguments[i] !== undefined) e.append(arguments[i]);
    return e;
  }

  window.Vetor = {
    RAIZ: RAIZ, token: token, chamar: chamar, el: el, icone: icone,
    me: function () { return carregarMe().then(function () { return me; }); },
    quando: new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short", timeZone: "America/Sao_Paulo" }),
    dia: new Intl.DateTimeFormat("pt-BR", { dateStyle: "medium", timeZone: "America/Sao_Paulo" }),
  };
})();
