# Metralhadora 3D

Uma metralhadora leve de esquadrão em 7,62 x 51, com desenho próprio, feita por código no Blender do mesmo jeito
que o `revolver-3d` e o `deagle-3d`. As proporções são as de uma Minimi 7.62 (medidas numa foto de lado), mas as
peças são desenho daqui. Mede uns 104 cm de comprimento e 26 cm de altura (da alça de transporte ao fundo da caixa
de munição) e tem uns 77 mil triângulos.

As peças ficam separadas:

- **Cano e frente:** cano pesado com quebra-chamas de cinco garras, bloco de gás com a massa de mira entre duas
  orelhas, tubo de gás, guarda-mão de polímero vazado e a alça de transporte presa no cano, com o punho voltado
  para trás.
- **Bipé:** dobrado para a frente, embaixo do cano, com as duas pernas de tubo e as sapatas.
- **Caixa da culatra:** chapas de reforço com rebites dos lados, alavanca de manejo à direita, janela da fita à
  esquerda e a tampa de alimentação em cima (com trilho, aletas e alça de mira de folha), que abre levantando
  atrás.
- **Punho e coronha:** guarda-mato, gatilho, punho com sulcos para os dedos e a coronha vazada com soleira de
  borracha.
- **Munição:** a caixa de 100 embaixo à esquerda, com a fita de elos subindo pelo lado até a bandeja, o cartucho
  da bandeja e o estojo que cai no tiro.

Aço fosfatado cinza, polímero cor de areia e a caixa de munição verde-oliva. Não tem logo nem escrita de marca.

## Animações

| Nome | Duração | O que faz |
|---|---|---|
| `tiro` | 3 quadros (0,1 s) | Gatilho, clarão grande, coice pequeno e o estojo caindo por baixo. O mod repete em sequência para fazer a rajada. |
| `recarregar` | 110 quadros (3,7 s) | A arma deita, a tampa abre, a caixa vazia sai puxando a fita e cai, a nova sobe, entra de lado deitando a fita na bandeja, a tampa fecha e a alavanca de manejo é puxada. |

No `metralhadora.blend` elas ficam em sequência na linha do tempo, com marcadores (tiro no quadro 5, recarregar
no 12). No `metralhadora.glb` cada uma vira uma animação com nome. O `.obj` sai parado e carregado.

## Onde estão os arquivos

| Arquivo | Para quê |
|---|---|
| `modelo/metralhadora.blend` | Abrir no Blender e mexer. Um objeto por peça. |
| `modelo/metralhadora.glb` | Visualizadores, Unity, Godot, Windows 3D Viewer. Em metros, com as animações. |
| `modelo/metralhadora.obj` (+ `.mtl`) | GameMaker e a maioria dos programas 3D. 1 unidade = 1 mm. |
| `modelo/animacoes.json` | Onde cada animação começa, quantos quadros tem e em que quadro acontece cada coisa (o mod lê). |
| `modelo/relatorio.txt` | Medidas e triângulos de cada peça e a conferência de peça atravessando peça. |
| `render/*.png` | Imagens do modo leve: lado direito, três quartos e um quadro de cada animação. |

## Como gerar de novo

Com o PC ocupado (ou jogando), use `gerar.bat --leve`: quatro imagens pequenas em prioridade mínima, em minuto e
meio. Com `gerar.bat --sem-render`, leva uns 5 segundos. Dois cliques no `gerar.bat` sem nada faz todas as imagens
em qualidade cheia e ocupa o processador inteiro por vários minutos. Precisa do Blender 5.2 em
`C:\Program Files\Blender Foundation`.

## Como mudar uma coisa

Tudo está no `gerar.py`, em milímetros:

- **Comprimento do cano:** troque `X_BOCA = 502.0` no começo do arquivo (o quebra-chamas, o bipé e o bloco de gás
  estão em números dentro de `construir()`, procure por `442`, `476` e `292`).
- **Quanto a tampa abre:** troque `TAMPA_ABERTA = math.radians(72)`.
- **Quanto a alavanca de manejo recua:** troque `CURSO_MANEJO = 118.0`.
- **Cores:** em `construir()`, procure `material("polimero", (0.20, 0.165, 0.10)` (areia),
  `material("caixa_municao", (0.075, 0.095, 0.045)` (verde) ou `material("aco_fosfatado", (0.22, 0.225, 0.235)`
  e mude os três números (vermelho, verde e azul, de 0 a 1).
- **Tamanho do clarão:** em `clarao()`, `radius1=15.0` e `depth=95` são a grossura e o comprimento do cone, e
  `48.0` é o tamanho da estrela.

O mod de Minecraft (`revolver-minecraft`) vai usar este modelo pelos nomes das peças e pelo `animacoes.json`:
renomear peça ou mudar quadro aqui exige mexer lá também.
