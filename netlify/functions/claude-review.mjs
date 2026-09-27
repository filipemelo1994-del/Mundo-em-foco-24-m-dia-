// Endpoint de revisão Claude (segunda opinião). Toda a lógica está em lib/review-core.mjs.
// Claude NÃO publica no Instagram e NÃO altera produção: este endpoint só devolve diagnóstico
// e correção proposta; quem decide e executa é o orquestrador.
import { createHandler } from "./lib/review-core.mjs";

export default createHandler();
