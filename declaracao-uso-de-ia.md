# Declaração de uso de assistência de inteligência artificial

Texto para o relatório técnico. Revise antes de inserir: os itens abaixo descrevem o que de fato
aconteceu até 13 de novembro de 2026, e precisam ser conferidos e ajustados pelo grupo se algo
mudar.

---

## Declaração

Este trabalho contou com assistência de um modelo de linguagem (Claude, da Anthropic) em parte das
suas etapas. A declaração abaixo detalha o que foi assistido, o que foi verificado e por quem, em
coerência com o princípio de rastreabilidade adotado no restante do projeto.

**Onde houve assistência:**

- redação do código de pré-processamento (`qc_uniplu.py`, notebooks 03 e 04) e dos seus testes;
- desenho dos procedimentos de diagnóstico da base de tempo, da fronteira do dia e do regime
  climático das partições;
- redação deste relatório, do dossiê de processo e dos registros em `achados/`;
- análise das saídas de execução e identificação de inconsistências nelas.

**Onde não houve assistência:**

- a escolha do problema, do recorte geográfico e temporal e das fontes de dados;
- a decisão de pré-registrar as escolhas metodológicas e o conteúdo do pré-registro;
- a execução de todo o código, que rodou nas máquinas dos integrantes;
- a decisão sobre cada emenda ao pré-registro.

**Como o conteúdo assistido foi verificado:**

- todo o código entregue foi executado e as suas saídas foram inspecionadas pelos integrantes; os
  números que constam deste relatório vêm dessas execuções, não de estimativas;
- os limiares de controle de qualidade foram conferidos contra a fonte citada (PINELO, 2026) e não
  contra a memória do modelo;
- nenhuma referência bibliográfica foi aceita sem verificação; referências cujos metadados não
  puderam ser confirmados foram deixadas de fora e estão listadas como pendência;
- os testes automatizados (18 asserções no notebook 03 e 23 no notebook 04) foram escritos para
  verificar o comportamento do código independentemente de quem o escreveu.

**Erros cometidos com assistência de IA, e como foram tratados:**

O uso de assistência produziu erros. Eles não foram apagados: estão registrados no dossiê de
processo, com a correção aplicada em cada caso. Entre eles, um critério de emenda mal formulado,
um procedimento de diagnóstico inadequado para a pergunta que fazia, um gargalo de autoencoder
incompatível com a comparação pretendida — que invalidou uma rodada inteira — e contagens de
estações que incluíam uma rede já excluída.

O registro desses erros faz parte do método adotado e não é acessório a ele.

---

## Nota para o grupo, não para o relatório

Dois pontos que valem checar antes de entregar:

1. Se algum integrante usou assistência de IA em outra etapa, isso precisa entrar na lista acima.
   A declaração vale pelo grupo inteiro.
2. Confirmem a política da disciplina sobre uso de IA. Esta declaração assume que o uso é
   permitido mediante declaração. Se a regra do professor for outra, a declaração muda.
