// Liga assinatura.js ao client.js oficial. Falha o build se o trecho esperado mudar numa atualização.
const fs = require("fs");
const file = process.argv[2];
let src = fs.readFileSync(file, "utf8");
const trocas = [
  ['const { getUserId, verify } = require("../crypto");',
   'const { getUserId, verify } = require("../crypto");\nconst { podeAssinar } = require("./assinatura");'],
  ['        } else {\n          return this.addSubscription(msg.routing_key, msg.options);\n        }',
   '        } else {\n          return podeAssinar(this.auth, msg.routing_key).then(ok => ok\n' +
   '            ? this.addSubscription(msg.routing_key, msg.options)\n' +
   '            : logger.warn(`assinatura recusada: ${msg.routing_key}`));\n        }'],
];
for (const [de, para] of trocas) {
  if (src.split(de).length !== 2) { console.error(`aplicar.js: trecho não encontrado uma única vez:\n${de}`); process.exit(1); }
  src = src.replace(de, para);
}
fs.writeFileSync(file, src);
console.log("aplicar.js: autorização de assinaturas ligada");
