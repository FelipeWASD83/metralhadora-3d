# CLAUDE.md: metralhadora-3d

Modelo 3D de uma metralhadora leve de esquadrão em 7,62 x 51, de desenho próprio, gerado por código no Blender, com
as animações de tiro em rajada e de recarga pela caixa de munição. Criado em 16/10/2026, a pedido do Felipe, numa
das seis sessões paralelas de armas novas para o mod `revolver-minecraft` (metralhadora, escopeta 12, AK-47, M4A4,
M4A1-S e sniper). Repositório público (escolha dele). O `CLAUDE.md` da raiz vale aqui também, e o `README.md`
explica o projeto para ele.

**Esta pasta faz só o modelo e as animações.** A integração no mod (munição, dano, Java, exportador) é da sessão
principal, uma arma por vez. Não mexer no `revolver-minecraft`, no `deagle-3d` nem no `revolver-3d` daqui.

## Como gerar e conferir

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --factory-startup --python gerar.py -- --leve
```

O `gerar.bat` faz o mesmo (sem opção, faz todas as imagens em qualidade cheia). As opções depois de `--`:

- `--sem-render` pula as imagens (uns 5 s);
- `--rapido` faz as imagens em meia resolução;
- `--leve` faz quatro imagens (lado direito, três quartos, `anim-tiro`, `anim-recarga`) com 4 núcleos e
  prioridade mínima, em ~1,5 min;
- `--vistas a,b` escolhe as imagens do modo leve. Os nomes estão no fim de `renderizar`.

**Ele joga no mesmo PC: sem ele pedir render cheio, conferir sempre com `--leve`.**

Conferir no `modelo/relatorio.txt`:

- todas as peças têm que sair `fechada`;
- não pode haver linha `ATENÇÃO`;
- a conferência das animações tem que dizer "nada novo" nos dez momentos (hoje diz). No repouso, a tampa encosta
  na caixa da culatra (10 triângulos), de propósito: ela assenta em cima.

## Referência medida

O Felipe escolheu **não** usar referência do CS2 para esta arma: o desenho é próprio. As proporções vêm da família
Minimi 7.62 / Mk 48 (metralhadora leve de 7,62 alimentada por fita), medidas na foto
`File:FN Minimi 7.62 Fixed Stock.jpg` do Wikimedia Commons (miniatura de 1920 px, lado esquerdo, inclinada uns 12°;
medido projetando os pontos no eixo do cano, ~1,87 px por mm, com 1.030 mm de comprimento total). Como a foto é um
pouco de três quartos, os números valem com uns 10% de folga. Contados da boca:

| O quê | Na foto | No modelo (X) |
|---|---|---|
| quebra-chamas | 0 a 60 mm | 442 a 502 |
| bloco de gás e massa de mira | ~200 mm | 292 a 332 |
| guarda-mão | 277 a 458 mm | 43 a 226 |
| frente da caixa da culatra | 458 mm | 44 |
| tampa de alimentação | 481 a 720 mm | 21 a -218 |
| face da culatra (cano de 502 mm do Minimi 7.62) | 502 mm | 0 |
| gatilho | 628 mm | -112 a -122 |
| fim da caixa da culatra | 766 mm | -264 |
| fim da coronha | ~1.030 mm | -528 (-542 com a soleira) |

Alturas a partir do eixo do cano: topo da tampa +56, fundo da caixa da culatra -54, fundo do punho -153, coronha
com ~130 mm de altura. A foto da `Mk 48 PEO Soldier.jpg` serviu para conferir o conjunto.

**O que é desenho próprio** (para não ficar cópia de Minimi): alça de transporte presa no cano à frente do
guarda-mão, com o punho voltado para trás por cima dele; guarda-mão de polímero areia envolvendo cano e tubo de gás,
vazado dos lados e em cima; quebra-chamas de cinco garras; massa de mira entre duas orelhas no bloco de gás; tampa
com trilho curto, aletas do lado direito e alça de mira de folha; chapas de reforço com rebites dos lados da caixa
da culatra; punho com três sulcos; coronha vazada com apoio de rosto; caixa de munição verde com nervuras, alça
de lona e trinco.

## Decisões que não se desfazem sem motivo

- **Eixos e unidade:** 1 unidade = 1 mm, boca em +X, lado direito de quem atira em -Y (alavanca de manejo e
  saída dos estojos), fita entrando pela esquerda (+Y), Z para cima, eixo do cano em Z = 0, X = 0 na face da
  culatra (a base do estojo na câmara).
- **Os utilitários de geometria são cópia dos do `deagle-3d`** (que já eram do `revolver-3d`): `almofada`,
  `prisma_x`, `tornear`, `cabo_solido`, `varrer`, `booleano`, `acabar` com normais pela área, `_juntar` recebendo
  o material, `Faixa`. Os projetos são independentes.
- **Cores:** aço fosfatado 0,22 (metálico 0,65, para não virar espelho), cano 0,20, peças pequenas 0,12, polímero
  areia (0,20; 0,165; 0,10), caixa de munição verde-oliva (0,075; 0,095; 0,045). Nada preto puro: no Minecraft vira
  borrão. Sem logo nem escrita de marca.
- **A caixa de munição é o `pente`** e leva a fita junto (a fita é parte da malha dela): cartuchos 7,62 a cada
  12,7 mm, um elo em volta de cada estojo, alternando a posição, e a aba que liga um elo ao próximo. A fita sai da
  bandeja para a esquerda, faz a curva para fora da caixa da culatra (em Y = 49) e desce reto até a boca da caixa.
  O cartucho da bandeja é o `estojo_topo` + `bala_topo`, filhos do `pente`.
- **A tampa de alimentação é articulada na frente** (dobradiça em X = 19, Z = 43) e abre 72° levantando atrás, como
  na Minimi. A alça de transporte fica à frente do guarda-mão justamente para a tampa não bater nela.
- **A alavanca de manejo é o `ferrolho`**: não vai e volta no tiro (arma de ferrolho aberto, a alavanca fica
  parada); só é puxada no fim da recarga.
- **O tiro tem exatamente 3 quadros** e o mod repete em rajada. O quadro 1 é o próprio disparo (clarão cheio,
  gatilho puxado, coice de 5 mm e 1,6°), o 2 tem o clarão menor e girado com o estojo saindo por baixo, o 3 é a
  arma no repouso com o estojo caindo. Repetido, não pula: do quadro 3 volta para o 1 como um tiro novo. O estojo
  que cai no quadro 3 some no 1 seguinte (é outro estojo).
- **Na recarga a caixa anda para a esquerda antes de cair** (puxa a fita para fora pela janela da esquerda) e a
  nova chega na altura certa do lado de fora e entra de lado: é isso que deita a fita na bandeja. Sem esse
  caminho a fita atravessaria a caixa da culatra.

## Contrato com o mod

- Empty raiz `metralhadora`, no punho (-185, 0, -105): o coice e a inclinação da recarga giram em volta dele. Tudo
  é filho dele; `estojo_topo` e `bala_topo` são filhos do `pente`.
- Peças que mexem: `ferrolho` (alavanca de manejo), `gatilho`, `tampa`, `pente` (origem no centro do fundo da caixa,
  (-16, 35, -172)), `estojo_topo` e `bala_topo` (o cartucho da bandeja, base em (-52, 10, 16)), `clarao` (escala 0
  em repouso, origem na boca) e `estojo_ejetado` (escala 0 em repouso, na câmara, mesma malha do `estojo_topo`).
  A raiz também tem chaves (coice e inclinação). O resto fica parado.
- Faixas de NLA: `repouso` (quadros 1 a 2, HOLD), `tiro` (5 a 7) e `recarregar` (12 a 121), sem sobrepor.
- `modelo/animacoes.json` repete isso com os eventos: `tiro` → `disparo` 1; `recarregar` → `tampa_abre` 13,
  `pente_sai` 25, `troca` 45 (a caixa velha sumiu nos quadros 43 a 47 e a nova ainda não apareceu),
  `pente_entra` 66, `tampa_fecha` 75, `ferrolho` 88 (alavanca toda para trás).

Renomear peça ou mudar quadro aqui quebra o mod depois de integrado: mudou, avisar a sessão do mod.

## O que não tem (de propósito, não foi pedido)

Sem vídeo das animações, sem fumaça, sem LOD, sem textura (tudo cor lisa), sem animação do bipé abrindo e sem
render cheio no commit (só os do `--leve`).
