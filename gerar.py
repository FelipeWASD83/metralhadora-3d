"""Gera o modelo 3D de uma metralhadora leve de esquadrão em 7,62 x 51 (desenho próprio, proporções da família
Minimi 7.62 / Mk 48), com as animações de tiro em rajada e de recarga pela caixa de munição.

Roda dentro do Blender (o mesmo caminho do revolver-3d e do deagle-3d):

    "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --factory-startup --python gerar.py -- --leve

Opções depois de `--`: `--sem-render` pula as imagens; `--rapido` faz as imagens em meia resolução e poucas
amostras; `--leve` é o rápido com 4 núcleos e prioridade mínima do Windows (dá para rodar com o PC ocupado);
`--vistas a,b` escolhe as imagens do modo leve.

Tudo em milímetros, 1 unidade do Blender = 1 mm. Eixos: X para a frente (a boca do cano aponta para +X), Y
largura (o lado direito de quem atira é -Y, onde fica a alavanca de manejo; a fita entra pela esquerda, +Y), Z para
cima. O eixo do cano é Z = 0 e X = 0 é a face da culatra (a base do estojo na câmara).

As peças de perfil (caixa da culatra, tampa, coronha, gatilho) são "almofadas": o perfil visto de lado, com os
cantos arredondados, extrudado em Y com a borda arredondada. O guarda-mão e o bloco de gás são o mesmo tipo de peça
deitada (a seção vista de frente, extrudada em X). O punho é um sólido de fatias ovais com sulcos para os dedos.
"""

import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

PASTA = Path(__file__).resolve().parent
SAIDA = PASTA / "modelo"
RENDER = PASTA / "render"
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

RAIZ = "metralhadora"              # nome do empty raiz (o mod procura por ele)
X_BOCA = 502.0                     # a boca do cano: cano de 502 mm contados da face da culatra
R_ALMA = 3.9                       # calibre 7,62
MEIA_CAIXA = 28.0                  # meia largura da caixa da culatra
X_FRENTE_CAIXA, X_TRAS_CAIXA = 44.0, -264.0
Z_TOPO, Z_BAIXO = 30.0, -54.0      # topo (onde assenta a tampa) e fundo da caixa da culatra
X_TRASEIRA = -528.0                # o fim da coronha (sem a soleira)
PIVO_TAMPA = (19.0, 0.0, 43.0)     # a dobradiça da tampa de alimentação, na frente
PIVO_GATILHO = (-112.0, 0.0, -50.0)
CARTUCHO_TOPO = (-52.0, 10.0, 16.0)            # a base do cartucho que está na bandeja, pronto para entrar
BASE_PENTE = Vector((-16.0, 35.0, -172.0))     # centro do fundo da caixa de munição
AVISOS = []

# ---------------------------------------------------------------- perfis 2D (x, z)

def _area(pts):
    n = len(pts)
    return 0.5 * sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))


def _sem_repetidos(pts):
    out = []
    for p in pts:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1e-4:
            out.append((p[0], p[1]))
    if len(out) > 2 and math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) < 1e-4:
        out.pop()
    return out


def arredondar(pts, raio_padrao, raio_min=0.0, passo_ang=math.radians(10)):
    """Arredonda cada canto do polígono fechado. Ponto pode ser (x, z) ou (x, z, raio)."""
    P = [(p[0], p[1], max(p[2] if len(p) > 2 else raio_padrao, raio_min)) for p in pts]
    n = len(P)
    out = []
    for i in range(n):
        x, z, r = P[i]
        ax, az = P[i - 1][:2]
        bx, bz = P[(i + 1) % n][:2]
        ux, uz = ax - x, az - z
        vx, vz = bx - x, bz - z
        la, lb = math.hypot(ux, uz), math.hypot(vx, vz)
        if la < 1e-6 or lb < 1e-6:
            continue
        ux, uz, vx, vz = ux / la, uz / la, vx / lb, vz / lb
        ang = math.acos(max(-1.0, min(1.0, ux * vx + uz * vz)))
        if r <= 0 or ang > math.radians(165):
            out.append((x, z))
            continue
        t = min(r / math.tan(ang / 2), 0.48 * la, 0.48 * lb)
        re = t * math.tan(ang / 2)
        bxv, bzv = ux + vx, uz + vz
        lbv = math.hypot(bxv, bzv)
        bxv, bzv = bxv / lbv, bzv / lbv
        d = re / math.sin(ang / 2)
        cx, cz = x + bxv * d, z + bzv * d
        sx, sz, ex, ez = x + ux * t, z + uz * t, x + vx * t, z + vz * t
        a0 = math.atan2(sz - cz, sx - cx)
        a1 = math.atan2(ez - cz, ex - cx)
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        m = max(2, math.ceil(abs(da) / passo_ang))
        for k in range(m + 1):
            a = a0 + da * k / m
            out.append((cx + re * math.cos(a), cz + re * math.sin(a)))
    return _sem_repetidos(out)


def recuar(pts, o):
    """Desloca o polígono para dentro em `o` (miter limitado)."""
    if o <= 0:
        return list(pts)
    n = len(pts)
    s = 1.0 if _area(pts) > 0 else -1.0
    out = []
    for i in range(n):
        px, pz = pts[i - 1]
        x, z = pts[i]
        qx, qz = pts[(i + 1) % n]
        d1x, d1z, d2x, d2z = x - px, z - pz, qx - x, qz - z
        l1, l2 = math.hypot(d1x, d1z), math.hypot(d2x, d2z)
        n1 = (-d1z * s / l1, d1x * s / l1)
        n2 = (-d2z * s / l2, d2x * s / l2)
        mx, mz = n1[0] + n2[0], n1[1] + n2[1]
        lm = math.hypot(mx, mz)
        if lm < 1e-9:
            mx, mz = n1
        else:
            mx, mz = mx / lm, mz / lm
        c = max(mx * n1[0] + mz * n1[1], 0.35)
        out.append((x + mx * o / c, z + mz * o / c))
    return out


def _cruza(pts):
    """True se o polígono fechado se cruza (O(n²), só para conferência)."""
    n = len(pts)

    def lado(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])

    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            c, d = pts[j], pts[(j + 1) % n]
            if lado(a, b, c) * lado(a, b, d) < 0 and lado(c, d, a) * lado(c, d, b) < 0:
                return True
    return False


def bez3(p0, p1, p2, p3, n=16):
    pts = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        pts.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return pts


def _sgnpow(v, e):
    return math.copysign(abs(v) ** e, v)


def _suave(a, b, t):
    t = max(0.0, min(1.0, (t - a) / (b - a)))
    return t * t * (3 - 2 * t)


def chaikin(pts, vezes=2):
    """Suaviza um caminho aberto mantendo as pontas."""
    for _ in range(vezes):
        novo = [pts[0]]
        for (ax, az), (bx, bz) in zip(pts, pts[1:]):
            novo += [(0.75 * ax + 0.25 * bx, 0.75 * az + 0.25 * bz), (0.25 * ax + 0.75 * bx, 0.25 * az + 0.75 * bz)]
        novo.append(pts[-1])
        pts = novo
    return pts


def _normais(caminho, lado):
    ns = []
    n = len(caminho)
    for i in range(n):
        ax, az = caminho[max(i - 1, 0)]
        bx, bz = caminho[min(i + 1, n - 1)]
        dx, dz = bx - ax, bz - az
        c = math.hypot(dx, dz)
        ns.append((lado * dz / c, -lado * dx / c))
    return ns


def _solido_de_aneis(nome, aneis, mat):
    bm = bmesh.new()
    vs = [[bm.verts.new(p) for p in anel] for anel in aneis]
    m = len(aneis[0])
    bm.faces.new(vs[0])
    bm.faces.new(vs[-1])
    for a, b in zip(vs, vs[1:]):
        for k in range(m):
            k2 = (k + 1) % m
            bm.faces.new([a[k], a[k2], b[k2], b[k]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4],
                          quad_method='BEAUTY', ngon_method='EAR_CLIP')
    return objeto(nome, bm, mat)


def varrer(nome, caminho, lado, meia_y, meia_n, mat, desloc=0.0, expoente=2.6, m=28):
    """Haste de seção oval arredondada correndo ao longo de um caminho (x, z).
    meia_y / meia_n: meia largura (em Y) e meia espessura (na normal), número ou função de t (0 a 1)."""
    fy = meia_y if callable(meia_y) else (lambda t: meia_y)
    fn = meia_n if callable(meia_n) else (lambda t: meia_n)
    ns = _normais(caminho, lado)
    aneis = []
    for i, ((x, z), (nx, nz)) in enumerate(zip(caminho, ns)):
        t = i / (len(caminho) - 1)
        wy, wn = fy(t), fn(t)
        cx, cz = x + nx * desloc, z + nz * desloc
        anel = []
        for k in range(m):
            a = 2 * math.pi * k / m
            dy = wy * _sgnpow(math.cos(a), 2 / expoente)
            dn = wn * _sgnpow(math.sin(a), 2 / expoente)
            anel.append((cx + nx * dn, dy, cz + nz * dn))
        aneis.append(anel)
    return _solido_de_aneis(nome, aneis, mat)


def _tampa_redonda(anel, f, b, centro_vizinho, w, raio, n):
    """Fatias extras que encolhem e se afastam da peça, arredondando uma ponta do cabo."""
    meio = (f + b) / 2
    eixo = (b - f).normalized()
    fora = Vector((eixo.y, -eixo.x))
    if fora.dot(meio - centro_vizinho) < 0:
        fora = -fora
    meio_l = (b - f).length / 2
    extras = []
    for k in range(1, n + 1):
        th = (math.pi / 2) * k / n
        enc, anda = raio * (1 - math.cos(th)), raio * math.sin(th)
        su, sy = max(1 - enc / meio_l, 0.05), max(1 - enc / w, 0.05)
        novo = []
        for (x, y, z) in anel:
            du = (Vector((x, z)) - meio).dot(eixo)
            pt = meio + eixo * du * su + fora * anda
            novo.append((pt.x, y * sy, pt.y))
        extras.append(novo)
    return extras


def cabo_solido(nome, frente, costas, largura, mat, m=64, expoente=2.0, raio_fundo=5.0, raio_topo=3.0,
                aneis_tampa=6, sulcos=None, alcance=0.42):
    """Cabo de madeira como sólido de fatias: cada fatia vai da linha da frente (lisa) à de trás e tem
    seção oval, com o volume puxado para trás (onde a palma encosta). `sulcos` (um valor por fatia,
    negativo = para dentro) afunda só a parte da frente da fatia, até `alcance` dela, para os sulcos
    dos dedos não ondularem os lados nem as costas. As duas pontas são arredondadas."""
    aneis = []
    for i, (f, b) in enumerate(zip(frente, costas)):
        t = i / (len(frente) - 1)
        w = largura(t)
        eixo = Vector((b[0] - f[0], b[1] - f[1])).normalized()
        sulco = sulcos[i] if sulcos else 0.0
        anel = []
        for k in range(m):
            a = 2 * math.pi * k / m
            u = 0.5 - 0.5 * _sgnpow(math.cos(a), 2 / expoente)
            u = u ** 0.86
            y = w * _sgnpow(math.sin(a), 2 / expoente)
            x, z = f[0] + (b[0] - f[0]) * u, f[1] + (b[1] - f[1]) * u
            if sulco and u < alcance:
                peso = (1 - u / alcance) ** 2
                x, z = x - eixo.x * sulco * peso, z - eixo.y * sulco * peso
            anel.append((x, y, z))
        aneis.append(anel)
    c = lambda i: (Vector(frente[i]) + Vector(costas[i])) / 2
    fundo = _tampa_redonda(aneis[-1], Vector(frente[-1]), Vector(costas[-1]), c(-2), largura(1.0),
                           raio_fundo, aneis_tampa)
    topo = _tampa_redonda(aneis[0], Vector(frente[0]), Vector(costas[0]), c(1), largura(0.0),
                          raio_topo, aneis_tampa)
    return _solido_de_aneis(nome, topo[::-1] + aneis + fundo, mat)


# ---------------------------------------------------------------- malhas

def objeto(nome, bm, mat=None):
    me = bpy.data.meshes.new(nome)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(nome, me)
    bpy.context.scene.collection.objects.link(ob)
    if mat:
        ob.data.materials.append(mat)
    return ob


def almofada(nome, pts, meia, r, mat, raio_canto=None, aneis=6):
    """Perfil (x, z) extrudado de -meia a +meia em Y com a borda arredondada de raio r."""
    base = arredondar(pts, raio_canto if raio_canto is not None else r * 1.3, raio_min=r * 1.15)
    niveis = []
    for k in range(aneis, -1, -1):
        th = (math.pi / 2) * k / aneis
        niveis.append((-(meia - r + r * math.sin(th)), r * (1 - math.cos(th))))
    for k in range(aneis + 1):
        th = (math.pi / 2) * k / aneis
        niveis.append((meia - r + r * math.sin(th), r * (1 - math.cos(th))))
    if _cruza(recuar(base, r)):
        AVISOS.append(f"{nome}: o contorno se cruza depois de recuar {r} mm (raio da borda grande demais)")
    bm = bmesh.new()
    aneis_v = []
    for y, o in niveis:
        aneis_v.append([bm.verts.new((x, y, z)) for x, z in recuar(base, o)])
    n = len(base)
    bm.faces.new(aneis_v[0])
    bm.faces.new(aneis_v[-1])
    for a, b in zip(aneis_v, aneis_v[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new([a[i], a[j], b[j], b[i]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4],
                          quad_method='BEAUTY', ngon_method='EAR_CLIP')
    return objeto(nome, bm, mat)


def tornear(nome, pts, mat, pos=(0, 0, 0), eixo='x', seg=64, fechado=False):
    """Sólido de revolução: pts = [(posição no eixo, raio)]; raio 0 vira ponta.
    `fechado` liga o último anel ao primeiro (tubos ocos)."""
    bm = bmesh.new()
    aneis = []
    for t, r in pts:
        if r < 1e-9:
            aneis.append([bm.verts.new((t, 0, 0))])
        else:
            aneis.append([bm.verts.new((t, r * math.cos(2 * math.pi * k / seg),
                                        r * math.sin(2 * math.pi * k / seg))) for k in range(seg)])
    pares = list(zip(aneis, aneis[1:]))
    if fechado:
        pares.append((aneis[-1], aneis[0]))
    for a, b in pares:
        for k in range(seg):
            k2 = (k + 1) % seg
            vs = []
            for v in (a[k % len(a)], a[k2 % len(a)], b[k2 % len(b)], b[k % len(b)]):
                if v not in vs:
                    vs.append(v)
            if len(vs) >= 3:
                bm.faces.new(vs)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if eixo == 'y':
        bmesh.ops.rotate(bm, verts=bm.verts[:], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'Z'))
    elif eixo == 'z':
        bmesh.ops.rotate(bm, verts=bm.verts[:], cent=(0, 0, 0), matrix=Matrix.Rotation(-math.pi / 2, 3, 'Y'))
    bmesh.ops.translate(bm, verts=bm.verts[:], vec=pos)
    return objeto(nome, bm, mat)


def caixa(nome, x0, x1, y0, y1, z0, z1, mat=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = ((x1 if v.co.x > 0 else x0), (y1 if v.co.y > 0 else y0), (z1 if v.co.z > 0 else z0))
    return objeto(nome, bm, mat)


def aplicar(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    novo = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    velho = ob.data
    nome = velho.name
    ob.modifiers.clear()
    ob.data = novo
    bpy.data.meshes.remove(velho)
    novo.name = nome


def booleano(base, ferramentas, op='DIFFERENCE'):
    if not ferramentas:
        return base
    col = bpy.data.collections.new("_ferramentas")
    bpy.context.scene.collection.children.link(col)
    for f in ferramentas:
        for c in list(f.users_collection):
            c.objects.unlink(f)
        col.objects.link(f)
    mod = base.modifiers.new("bool", 'BOOLEAN')
    mod.operation = op
    mod.solver = 'MANIFOLD'
    mod.operand_type = 'COLLECTION'
    mod.collection = col
    aplicar(base)
    for f in list(col.objects):
        malha = f.data
        bpy.data.objects.remove(f)
        bpy.data.meshes.remove(malha)
    bpy.data.collections.remove(col)
    return base


def acabar(ob, bisel=0.0, segmentos=3, angulo=36):
    """Chanfro opcional nas quinas vivas e sombreamento liso só onde a curva é suave."""
    if bisel > 0:
        m = ob.modifiers.new("bisel", 'BEVEL')
        m.width = bisel
        m.segments = segmentos
        m.limit_method = 'ANGLE'
        m.angle_limit = math.radians(50)
        aplicar(ob)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    lim = math.radians(angulo)
    for e in bm.edges:
        e.smooth = not (len(e.link_faces) == 2 and e.calc_face_angle(0.0) > lim)
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(ob.data)
    bm.free()
    m = ob.modifiers.new("normais", 'WEIGHTED_NORMAL')
    m.mode = 'FACE_AREA'
    m.keep_sharp = True
    aplicar(ob)
    return ob


def girar(ob, rot, loc):
    ob.rotation_euler = rot
    ob.location = loc
    return ob



# ---------------------------------------------------------------- materiais e texturas

def material(nome, cor, metal=0.0, rug=0.5, imagem=None, verniz=0.0):
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*cor, 1)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rug
    if verniz:
        b.inputs["Coat Weight"].default_value = verniz
        b.inputs["Coat Roughness"].default_value = 0.12
    if imagem:
        t = m.node_tree.nodes.new("ShaderNodeTexImage")
        t.image = imagem
        m.node_tree.links.new(t.outputs["Color"], b.inputs["Base Color"])
    return m


def _juntar(base, extra, mat):
    """Põe a malha de `extra` dentro de `base`, com o material dado, e apaga `extra`. O índice é procurado pelo
    material: o booleano deixa espaços vazios na lista de materiais da peça."""
    nomes = [m.name if m else None for m in base.data.materials]
    if mat.name not in nomes:
        base.data.materials.append(mat)
        nomes.append(mat.name)
    indice_material = nomes.index(mat.name)
    bm = bmesh.new()
    bm.from_mesh(extra.data)
    for f in bm.faces:
        f.material_index = indice_material
    tmp = bpy.data.meshes.new("_tmp")
    bm.to_mesh(tmp)
    bm.free()
    bm = bmesh.new()
    bm.from_mesh(base.data)
    bm.from_mesh(tmp)
    bm.to_mesh(base.data)
    bm.free()
    malha = extra.data
    bpy.data.objects.remove(extra)
    bpy.data.meshes.remove(malha)
    bpy.data.meshes.remove(tmp)


def _pivo(ob, ponto):
    """Muda a origem da peça para o ponto em que ela gira, sem mexer na forma (peça sem transformação)."""
    p = Vector(ponto)
    ob.data.transform(Matrix.Translation(-p))
    ob.location = p


def _prender(filho, pai):
    mw = filho.matrix_world.copy()
    filho.parent = pai
    filho.matrix_world = mw


class Faixa:
    """Uma animação com nome (vira uma faixa de NLA e uma animação no GLB). As chaves de cada peça vão
    de 1 a `fim`, para todas começarem e acabarem juntas."""

    def __init__(self, nome, inicio, fim, extrapolacao='NOTHING'):
        self.nome, self.inicio, self.fim, self.extrapolacao = nome, inicio, fim, extrapolacao
        self.chaves = {}

    def k(self, ob, prop, quadro, valor, interp='BEZIER'):
        self.chaves.setdefault(ob, []).append((quadro, prop, tuple(valor), interp))

    def gravar(self, repouso):
        from bpy_extras import anim_utils
        for ob, lista in self.chaves.items():
            por_prop = {}
            for c in lista:
                por_prop.setdefault(c[1], []).append(c)
            ob.animation_data_create()
            ob.animation_data.action = None
            interps = {}
            for prop, cs in por_prop.items():
                cs.sort(key=lambda c: c[0])
                if cs[0][0] > 1:
                    cs.insert(0, (1, prop, cs[0][2], 'CONSTANT'))
                if cs[-1][0] < self.fim:
                    cs.append((self.fim, prop, cs[-1][2], 'CONSTANT'))
                for quadro, _, valor, interp in cs:
                    setattr(ob, prop, valor)
                    ob.keyframe_insert(prop, frame=quadro)
                    interps[(prop, quadro)] = interp
            acao = ob.animation_data.action
            # o keyframe_insert ignora a interpolação pedida: grava chave por chave na curva
            canais = anim_utils.action_get_channelbag_for_slot(acao, ob.animation_data.action_slot)
            for fc in canais.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = interps.get((fc.data_path, round(kp.co.x)), 'BEZIER')
            acao.name = f"{self.nome}|{ob.name}"
            trilha = ob.animation_data.nla_tracks.new()
            trilha.name = self.nome
            faixa = trilha.strips.new(self.nome, self.inicio, acao)
            faixa.extrapolation = self.extrapolacao
            ob.animation_data.action = None
            for prop, valor in repouso[ob].items():
                setattr(ob, prop, valor)


def luz_de_estudio(nome, pos, alvo, tam, forca):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
    for v in bm.verts:
        v.co = (v.co.x * tam[0] * 2, v.co.y * tam[1] * 2, 0)
    ob = objeto(nome, bm)
    d = Vector(alvo) - Vector(pos)
    ob.rotation_euler = d.to_track_quat('Z', 'Y' if abs(d.normalized().z) < 0.9 else 'X').to_euler()
    ob.location = pos
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    nodes = m.node_tree.nodes
    nodes.clear()
    em = nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = forca
    saida = nodes.new("ShaderNodeOutputMaterial")
    m.node_tree.links.new(em.outputs["Emission"], saida.inputs["Surface"])
    ob.data.materials.append(m)
    ob.visible_camera = False
    ob.visible_shadow = False
    return ob


def prisma_x(nome, pts_yz, x0, x1, r, mat):
    """Seção vista de frente (y, z), cantos arredondados, extrudada em X de x0 a x1 com a borda de raio r."""
    ob = almofada(nome, pts_yz, (x1 - x0) / 2, r, mat)
    ob.data.transform(Matrix.Translation(((x0 + x1) / 2, 0, 0)) @ Matrix.Rotation(-math.pi / 2, 4, 'Z'))
    return ob

def deslocar(ob, v):
    ob.data.transform(Matrix.Translation(v))
    return ob


def pino(nome, x, z, raio, meia, mat):
    perfil = [(-meia, 0), (-meia, raio * 0.8), (-meia + 0.5, raio), (meia - 0.5, raio), (meia, raio * 0.8), (meia, 0)]
    return acabar(tornear(nome, perfil, mat, pos=(x, 0, z), eixo='y', seg=32))


# ---------------------------------------------------------------- a metralhadora

# 7,62 x 51: estojo de 51,2 mm (aro de 12 mm, ombro, gargalo) e ponta encamisada; a base do estojo em x = 0
PERFIL_ESTOJO = [(0, 0), (0, 5.3), (0.4, 6.0), (1.3, 6.0), (1.5, 5.1), (2.7, 5.1), (3.3, 5.97), (39.6, 5.77),
                 (43.3, 4.39), (51.0, 4.39), (51.2, 4.15), (51.2, 0)]
PERFIL_BALA = [(46, 0), (46, 3.91), (54, 3.91), (60, 3.45), (65.5, 2.4), (69.6, 1.0), (71.1, 0)]
PASSO_FITA = 12.7                  # distância entre dois cartuchos da fita


def caminho_fita():
    """O caminho da fita visto de frente (y, z): sai da bandeja para a esquerda, faz a curva para fora da caixa da
    culatra e desce reto até a boca da caixa de munição. Devolve um ponto a cada PASSO_FITA, começando no cartucho
    da bandeja."""
    y0, z0 = CARTUCHO_TOPO[1], CARTUCHO_TOPO[2]
    denso = [(y0 + t, z0) for t in np.linspace(0, 23, 47)]
    cy, raio = y0 + 23, 16.0
    for k in range(1, 41):
        a = (math.pi / 2) * k / 40
        denso.append((cy + raio * math.sin(a), z0 - raio + raio * math.cos(a)))
    for z in np.linspace(z0 - raio - 1, z0 - raio - 90, 90):
        denso.append((cy + raio, float(z)))
    pts, andado, proximo = [denso[0]], 0.0, PASSO_FITA
    for (ay, az), (by, bz) in zip(denso, denso[1:]):
        seg = math.hypot(by - ay, bz - az)
        while andado + seg >= proximo:
            t = (proximo - andado) / seg
            pts.append((ay + (by - ay) * t, az + (bz - az) * t))
            proximo += PASSO_FITA
        andado += seg
    return [p for p in pts if p[1] > -67]


def construir():
    """Proporções de uma metralhadora leve de 7,62 (família Minimi 7.62 / Mk 48), medidas numa foto de lado, com
    desenho próprio: cano pesado exposto com quebra-chamas de cinco garras, guarda-mão vazado, bloco de gás com a
    massa de mira entre orelhas, bipé dobrado para a frente embaixo do cano, alça de transporte na frente do
    guarda-mão, caixa da culatra com a tampa de alimentação articulada na frente, punho com sulcos para os dedos,
    coronha vazada e a caixa de munição de 100 embaixo à esquerda, com a fita subindo pelo lado até a bandeja."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    metal = material("aco_fosfatado", (0.22, 0.225, 0.235), metal=0.65, rug=0.48)
    aco_cano = material("aco_cano", (0.20, 0.20, 0.205), metal=1.0, rug=0.34)
    escuro = material("aco_escuro", (0.12, 0.12, 0.125), metal=0.85, rug=0.5)
    polimero = material("polimero", (0.20, 0.165, 0.10), rug=0.68)
    borracha = material("borracha", (0.045, 0.045, 0.048), rug=0.9)
    verde = material("caixa_municao", (0.075, 0.095, 0.045), metal=0.3, rug=0.55)
    P = {}

    # ---- cano pesado: fino dentro da caixa da culatra, grosso no guarda-mão, um degrau no bloco de gás e outro
    # antes da rosca do quebra-chamas; alma 7,62 raiada
    cano = tornear("cano", [(-0.5, 0), (-0.5, 7.2), (28, 7.2), (30, 13), (226, 13), (232, 12.5), (334, 12.5),
                            (340, 11.5), (436, 11.5), (438, 10), (446, 10), (446, 0)], aco_cano)
    cortes = [tornear("_alma", [(-2, 0), (-2, R_ALMA), (X_BOCA + 5, R_ALMA), (X_BOCA + 5, 0)], None, seg=48)]
    cortes += [girar(caixa(f"_raia{k}", 300, X_BOCA + 5, -0.6, 0.6, R_ALMA - 0.3, R_ALMA + 0.35),
                     (math.radians(15 + 90 * k), 0, 0), (0, 0, 0)) for k in range(4)]
    cortes += [tornear(f"_anel_cano{k}", [(380 + 14 * k, 11), (383 + 14 * k, 11), (383 + 14 * k, 13),
                                          (380 + 14 * k, 13)], None, seg=64, fechado=True) for k in range(3)]
    booleano(cano, cortes)
    P["cano"] = acabar(cano)

    qc = tornear("quebra_chamas", [(440, 0), (440, 10.4), (443, 11.3), (498, 11.3), (502, 10.2), (502, 0)], metal)
    cortes = [tornear("_boca_qc", [(436, 0), (436, 6.4), (X_BOCA + 6, 6.4), (X_BOCA + 6, 0)], None, seg=48),
              tornear("_sulco_qc", [(452, 10.2), (456, 10.2), (456, 12), (452, 12)], None, seg=64, fechado=True)]
    cortes += [girar(caixa(f"_garra{k}", 464, X_BOCA + 6, -1.7, 1.7, 4, 14), (math.radians(90 + 72 * k), 0, 0),
                     (0, 0, 0)) for k in range(5)]
    booleano(qc, cortes)
    P["quebra_chamas"] = acabar(qc, 0.2, 2)

    # ---- guarda-mão de polímero em volta do cano e do tubo de gás, vazado dos lados e em cima
    secao = [(-26, 14, 5), (-30, 0, 5), (-28, -30, 6), (-18, -42, 5), (18, -42, 5), (28, -30, 6), (30, 0, 5),
             (26, 14, 5), (14, 24, 4), (-14, 24, 4)]
    guarda_mao = prisma_x("guarda_mao", secao, X_FRENTE_CAIXA - 1, 226, 2.0, polimero)
    cortes = [tornear("_furo_cano", [(30, 0), (30, 14), (240, 14), (240, 0)], None, seg=48),
              tornear("_furo_gas", [(30, 0), (30, 7.2), (240, 7.2), (240, 0)], None, pos=(0, 0, -24), seg=32)]
    for k in range(6):
        x = 64 + 25 * k
        cortes += [caixa(f"_ventilacao_e{k}", x, x + 14, 9, 40, -11, 1),
                   caixa(f"_ventilacao_d{k}", x, x + 14, -40, -9, -11, 1),
                   caixa(f"_ventilacao_t{k}", x + 3, x + 11, -6, 6, 8, 30)]
    cortes += [caixa(f"_frisos_baixo{k}", 58 + 12 * k, 62 + 12 * k, -20, 20, -46, -40.5) for k in range(14)]
    booleano(guarda_mao, cortes)
    P["guarda_mao"] = acabar(guarda_mao, 0.3, 2, angulo=40)

    # ---- tubo de gás, bloco de gás com a massa de mira entre duas orelhas
    P["tubo_gas"] = acabar(tornear("tubo_gas", [(200, 0), (200, 6), (300, 6), (300, 0)], metal, pos=(0, 0, -24),
                                   seg=32))
    bloco = prisma_x("bloco_gas", [(-16, 16, 4), (-16, -30, 5), (-10, -38, 3), (10, -38, 3), (16, -30, 5),
                                   (16, 16, 4)], 292, 332, 1.5, metal)
    booleano(bloco, [caixa("_entalhe_bloco_e", 300, 324, 13, 20, -26, -6),
                     caixa("_entalhe_bloco_d", 300, 324, -20, -13, -26, -6)])
    P["bloco_gas"] = acabar(bloco, 0.3, 2)
    mira = almofada("massa_mira", [(307, 14), (315, 14), (314, 53), (308, 53)], 1.5, 0.5, escuro)
    for s in (-1, 1):
        orelha = deslocar(almofada(f"_orelha{s}", [(298, 14), (324, 14), (322, 46), (319, 58), (303, 58), (300, 46)],
                                   1.6, 0.6, None), (0, s * 7.5, 0))
        _juntar(mira, acabar(orelha), escuro)
    P["massa_mira"] = acabar(mira)

    # ---- bipé dobrado para a frente: articulação embaixo do bloco de gás, duas pernas de tubo com o tubo de
    # dentro mais fino e as sapatas viradas para cima
    bipe = almofada("bipe", [(298, -34), (326, -34), (326, -44), (318, -51), (306, -51), (298, -44)], 17, 2.0, metal)
    _juntar(bipe, pino("_eixo_bipe", 312, -43, 3.0, 19.5, escuro), escuro)
    for s in (-1, 1):
        perna = tornear(f"_perna{s}", [(306, 0), (306, 5.4), (418, 5.4), (421, 4.4), (474, 4.4), (476, 3.4),
                                       (476, 0)], None, pos=(0, s * 10.5, -43), seg=24)
        _juntar(bipe, acabar(perna), metal)
        pe = deslocar(almofada(f"_sapata{s}", [(468, -50), (496, -46), (498, -40), (470, -38)], 3.2, 1.0, None),
                      (0, s * 10.5, 0))
        _juntar(bipe, acabar(pe), escuro)
    P["bipe"] = bipe

    # ---- alça de transporte: abraçadeira no cano logo à frente do guarda-mão, braço curvo e o punho de polímero
    # voltado para trás, por cima do guarda-mão
    alca = acabar(tornear("alca", [(229, 12.6), (251, 12.6), (251, 18.5), (229, 18.5)], metal, seg=48, fechado=True))
    braco = varrer("_braco_alca", chaikin([(240, 14), (240, 40), (231, 60), (214, 72), (204, 74)], 2), -1, 5.5, 4.2,
                   None)
    _juntar(alca, acabar(braco, angulo=40), metal)
    punho_alca = tornear("_punho_alca", [(118, 0), (118, 8.0), (121, 9.6), (204, 9.6), (208, 8.0), (208, 0)], None,
                         pos=(0, 0, 76), seg=32)
    booleano(punho_alca, [tornear(f"_estria_alca{k}", [(128 + 9 * k, 8.9), (131 + 9 * k, 8.9), (131 + 9 * k, 11),
                                                       (128 + 9 * k, 11)], None, pos=(0, 0, 76), seg=32,
                                  fechado=True) for k in range(8)])
    _juntar(alca, acabar(punho_alca), polimero)
    P["alca"] = alca

    # ---- caixa da culatra: bandeja e janela de alimentação à esquerda, janela de ejeção embaixo, trilho do
    # manejo à direita e dois frisos de cada lado
    armacao = almofada("armacao", [(X_FRENTE_CAIXA, Z_TOPO, 3), (X_FRENTE_CAIXA, -36, 5), (28, Z_BAIXO, 5),
                                   (X_TRAS_CAIXA, Z_BAIXO, 4), (X_TRAS_CAIXA, Z_TOPO, 3)], MEIA_CAIXA, 3.0, metal)
    cortes = [caixa("_bandeja", -62, 26, 0, 40, 8, 40),
              caixa("_ejecao", -70, -8, -12, 12, Z_BAIXO - 6, -44),
              caixa("_trilho_manejo", -160, 4, -40, -23, -1, 11)]
    for z in (-21, -39):
        cortes += [caixa(f"_friso_e{z}", -250, 32, MEIA_CAIXA - 1.4, MEIA_CAIXA + 4, z - 1.6, z + 1.6),
                   caixa(f"_friso_d{z}", -250, 32, -MEIA_CAIXA - 4, -MEIA_CAIXA + 1.4, z - 1.6, z + 1.6)]
    booleano(armacao, cortes)
    acabar(armacao, 0.4, 2)
    # chapas de reforço levantadas dos dois lados, com rebites
    for lado in (-1, 1):
        chapa = deslocar(almofada(f"_chapa{lado}", [(-236, -48), (-96, -48), (-80, -30), (30, -30), (30, -8),
                                                   (-236, -8)], 1.0, 0.45, None, raio_canto=4),
                         (0, lado * (MEIA_CAIXA + 0.4), 0))
        _juntar(armacao, acabar(chapa), metal)
        for k, x in enumerate((-226, -150, -60, 20)):
            for z in (-40, -16):
                rebite = tornear(f"_rebite{lado}{k}{z}", [(0, 0), (0, 2.2), (0.6, 2.0), (1.1, 1.2), (1.3, 0)],
                                 None, pos=(x, lado * (MEIA_CAIXA + 1.2), z), eixo='y', seg=16)
                if lado < 0:     # a cabeça virada para fora do lado direito
                    centro = Vector((x, lado * (MEIA_CAIXA + 1.2), z))
                    rebite.data.transform(Matrix.Translation(centro) @ Matrix.Rotation(math.pi, 4, 'Z')
                                          @ Matrix.Translation(-centro))
                _juntar(armacao, acabar(rebite), escuro)
    P["armacao"] = armacao
    P["bandeja"] = acabar(deslocar(almofada("bandeja", [(-60, 6.0), (24, 6.0), (24, 8.6), (-60, 8.6)], 15, 0.8,
                                            escuro), (0, 14, 0)))
    P["encaixe"] = acabar(caixa("encaixe", -80, 40, 14, 30, -59, Z_BAIXO + 0.5, metal), 0.5, 2)
    for k, (x, z) in enumerate([(-242, -8), (-242, -40), (22, -28), (-196, 14), (-120, -30)]):
        P[f"pino{k + 1}"] = pino(f"pino{k + 1}", x, z, 2.6, MEIA_CAIXA + 0.6, escuro)

    # ---- caixa do gatilho, guarda-mato e punho com sulcos para os dedos
    cg = almofada("caixa_gatilho", [(-88, -50), (-215, -50), (-215, -68), (-150, -71), (-92, -71)], 14, 2.5, metal)
    booleano(cg, [caixa("_fenda_gatilho", -125, -103, -3.6, 3.6, -76, -49)])
    P["caixa_gatilho"] = acabar(cg, 0.3, 2)
    P["pino_gatilho"] = pino("pino_gatilho", PIVO_GATILHO[0], PIVO_GATILHO[2], 1.8, 14.6, escuro)
    linha = chaikin([(-96, -64), (-97, -80), (-104, -92), (-122, -97), (-142, -94), (-156, -80)], 2)
    P["guarda_mato"] = acabar(varrer("guarda_mato", linha, -1, 6.0, 2.6, metal, expoente=3.0), angulo=40)
    P["gatilho"] = acabar(almofada("gatilho", [(-106, -53), (-115, -53), (-116, -63), (-118, -73), (-122, -83),
                                               (-119, -86, 1.5), (-114, -79), (-110, -69), (-107, -61)], 3.0, 0.9,
                                   escuro))

    n = 20
    inclina = math.radians(16)
    frente, costas, sulcos = [], [], []
    for i in range(n):
        t = i / (n - 1)
        s = 96 * t
        bojo = 6 * math.sin(math.pi * min(1.0, t * 1.15))
        frente.append((-150 - s * math.sin(inclina), -62 - s * math.cos(inclina)))
        costas.append((-197 - s * math.sin(inclina) - bojo * math.cos(inclina),
                       -58 - s * math.cos(inclina) + bojo * math.sin(inclina)))
        u = (t - 0.14) / 0.74
        sulcos.append(-2.4 * (0.5 - 0.5 * math.cos(2 * math.pi * 3 * u)) if 0 <= u <= 1 else 0.0)
    punho = cabo_solido("empunhadura", frente, costas, lambda t: 14 + 1.6 * math.sin(math.pi * t) + 1.2 * t * t,
                        polimero, m=48, expoente=2.2, raio_fundo=4.0, raio_topo=2.0, sulcos=sulcos, alcance=0.4)
    P["empunhadura"] = acabar(punho, angulo=40)

    # ---- coronha de polímero vazada, com apoio de rosto subindo para trás e soleira de borracha
    coronha = almofada("coronha", [(-262, 30, 2), (-300, 28, 10), (-462, 34, 20), (X_TRASEIRA, 36, 3),
                                   (X_TRASEIRA, -104, 3), (-452, -104, 12), (-418, -80, 30), (-350, -56, 30),
                                   (-262, -50, 2)], 21, 4.5, polimero)
    vazado = almofada("_vazado", [(-324, -4), (-446, 6), (-470, -24), (-458, -66), (-442, -76), (-354, -42)], 30, 0.5,
                      None, raio_canto=12)
    booleano(coronha, [vazado])
    P["coronha"] = acabar(coronha, 0.6, 2, angulo=40)
    P["soleira"] = acabar(almofada("soleira", [(X_TRASEIRA + 2, 38, 3), (X_TRASEIRA - 12, 36, 4),
                                               (X_TRASEIRA - 14, -100, 4), (X_TRASEIRA + 2, -106, 3)], 22, 3.0,
                                   borracha), angulo=40)

    # ---- tampa de alimentação, articulada na frente: sulcos em cima, aletas à direita, alça de mira de folha e o
    # trinco atrás
    tampa = almofada("tampa", [(21, Z_TOPO, 2), (21, 41, 7), (11, 55, 8), (-186, 57, 5), (-218, 52, 4),
                               (-218, Z_TOPO, 2)], 27, 2.5, metal)
    cortes = [caixa(f"_aleta{k}", -160 + 20 * k, -152 + 20 * k, -32, -24.6, 36, 50) for k in range(7)]
    booleano(tampa, cortes)
    acabar(tampa, 0.3, 2)
    base_mira = almofada("_base_alca_mira", [(-210, 55), (-184, 55), (-184, 62), (-210, 62)], 10, 1.2, None)
    folha = almofada("_folha", [(-201, 60), (-193, 60), (-194, 78), (-200, 78)], 7, 1.0, None)
    booleano(folha, [tornear("_orificio", [(-10, 0), (-10, 2.2), (10, 2.2), (10, 0)], None, pos=(-197, 0, 71.5),
                             eixo='y', seg=24)])
    trilho = prisma_x("_trilho", [(-10.5, 55.5), (-10.5, 59), (-8, 62), (8, 62), (10.5, 59), (10.5, 55.5)],
                      -172, -24, 0.5, None)
    booleano(trilho, [caixa(f"_fenda_trilho{k}", -166 + 10 * k, -161 + 10 * k, -12, 12, 59.6, 64) for k in range(14)])
    trinco = almofada("_trinco", [(-228, 33), (-214, 33), (-214, 49), (-228, 46)], 20, 1.5, None)
    dobradica = pino("_dobradica", PIVO_TAMPA[0], PIVO_TAMPA[2], 3.4, 23, None)
    for peca in (base_mira, folha, trilho, trinco, dobradica):
        _juntar(tampa, acabar(peca, 0.15, 2), escuro)
    P["tampa"] = tampa

    # ---- alavanca de manejo (à direita): a placa corre no trilho da caixa da culatra, a haste sai para fora e
    # termina num punho de polímero
    manejo = deslocar(almofada("ferrolho", [(-26, 0.5), (-6, 0.5), (-6, 9.5), (-26, 9.5)], 2.0, 0.6, escuro),
                      (0, -25.5, 0))
    haste = tornear("_haste", [(-27, 0), (-27, 3.2), (-46, 3.2), (-46, 0)], None, pos=(-16, 0, 5), eixo='y', seg=24)
    punho_manejo = tornear("_punho_manejo", [(-44, 0), (-44, 6.0), (-46, 7.2), (-58, 7.2), (-60, 6.0), (-60, 0)],
                           None, pos=(-16, 0, 5), eixo='y', seg=32)
    _juntar(manejo, acabar(haste), escuro)
    _juntar(manejo, acabar(punho_manejo), polimero)
    P["ferrolho"] = acabar(manejo)

    municao(P, verde, escuro)
    clarao(P)
    return P


def municao(P, verde, escuro):
    """Caixa de munição de 100 (o `pente`), com a fita de elos subindo pelo lado esquerdo até a bandeja. O cartucho
    da bandeja é o `estojo_topo` + `bala_topo`, filhos da caixa; o estojo que cai no tiro usa a mesma malha."""
    latao = material("latao", (0.80, 0.6, 0.34), metal=1.0, rug=0.3)
    espoleta = material("espoleta", (0.62, 0.6, 0.56), metal=1.0, rug=0.35)
    cobre = material("cobre", (0.72, 0.42, 0.26), metal=1.0, rug=0.32)
    x0, x1, y0, y1, z0, z1 = -86, 54, 0, 70, BASE_PENTE.z, -60.5
    pente = deslocar(almofada("pente", [(x0, z0), (x1, z0), (x1, z1), (x0, z1)], (y1 - y0) / 2, 3.0, verde,
                              raio_canto=7), (0, (y0 + y1) / 2, 0))
    cortes = [caixa("_boca", -62, 26, 40, 58, -74, -55)]
    for k in range(4):
        z = -156 + 21 * k
        cortes += [caixa(f"_nervura_e{k}", x0 + 12, x1 - 12, y1 - 1.2, y1 + 4, z - 2, z + 2),
                   caixa(f"_nervura_d{k}", x0 + 12, x1 - 12, y0 - 4, y0 + 1.2, z - 2, z + 2)]
    cortes += [caixa("_tampa_caixa_f", x1 - 1.2, x1 + 4, y0 + 8, y1 - 8, -76, -73.5),
               caixa("_tampa_caixa_t", x0 - 4, x0 + 1.2, y0 + 8, y1 - 8, -76, -73.5)]
    booleano(pente, cortes)
    acabar(pente, 0.3, 2)
    trinco = deslocar(almofada("_trinco_caixa", [(x1 - 1, -80), (x1 + 6, -82), (x1 + 6, -98), (x1 - 1, -100)], 11,
                               1.2, None), (0, (y0 + y1) / 2, 0))
    dobradica = tornear("_dobradica_caixa", [(x0 + 6, 0), (x0 + 6, 3.4), (x1 - 6, 3.4), (x1 - 6, 0)], None,
                        pos=(0, y1 - 1, z1 - 2), seg=24)
    alca = deslocar(varrer("_alca_caixa", chaikin([(-50, -102), (-50, -90), (-40, -84), (20, -84), (30, -90),
                                                     (30, -102)], 2), -1, 2.0, 2.2, None), (0, y1 + 1.4, 0))
    for peca in (trinco, dobradica, alca):
        _juntar(pente, acabar(peca), escuro)

    # a fita: cartucho, elo (anel em volta do estojo, alternando a posição) e a aba que liga um elo ao próximo
    pts = caminho_fita()
    xc = CARTUCHO_TOPO[0]
    for i, (y, z) in enumerate(pts):
        if i > 0:
            _juntar(pente, acabar(tornear(f"_estojo_fita{i}", PERFIL_ESTOJO, None, pos=(xc, y, z), seg=20)), latao)
            _juntar(pente, acabar(tornear(f"_bala_fita{i}", PERFIL_BALA, None, pos=(xc, y, z), seg=20)), cobre)
        xa, xb = (xc + 7, xc + 15) if i % 2 == 0 else (xc + 21, xc + 29)
        _juntar(pente, acabar(tornear(f"_elo{i}", [(xa, 6.05), (xb, 6.05), (xb, 6.9), (xa, 6.9)], None,
                                      pos=(0, y, z), seg=20, fechado=True)), escuro)
        if i + 1 < len(pts):
            ny, nz = pts[i + 1]
            dy, dz = ny - y, nz - z
            comp = math.hypot(dy, dz)
            fora = (-dz / comp, dy / comp)
            aba = caixa(f"_aba{i}", xa, xb, -comp / 2 - 2, comp / 2 + 2, -0.7, 0.7)
            aba.data.transform(Matrix.Translation((0, (y + ny) / 2 + fora[0] * 6.5, (z + nz) / 2 + fora[1] * 6.5))
                               @ Matrix.Rotation(math.atan2(dz, dy), 4, 'X'))
            _juntar(pente, aba, escuro)
    _pivo(pente, BASE_PENTE)
    P["pente"] = pente

    estojo = tornear("estojo_ejetado", PERFIL_ESTOJO, latao, seg=40)
    _juntar(estojo, tornear("_espoleta", [(-0.1, 0), (-0.1, 2.3), (0.2, 2.3), (0.2, 0)], None, seg=24), espoleta)
    acabar(estojo)
    bala = acabar(tornear("bala_topo", PERFIL_BALA, cobre, seg=40))
    topo = bpy.data.objects.new("estojo_topo", estojo.data)
    bpy.context.scene.collection.objects.link(topo)
    topo.location = CARTUCHO_TOPO
    bala.location = CARTUCHO_TOPO
    P["estojo_ejetado"], P["estojo_topo"], P["bala_topo"] = estojo, topo, bala


def clarao(P):
    """O clarão da boca: um cone de fogo comprido e uma estrela de dez pontas, com a origem na boca do cano. Maior
    que o da deagle, porque é uma 7,62 de cano longo atirando em rajada."""
    mat = material("clarao", (1.0, 0.78, 0.4))
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Emission Color"].default_value = (1.0, 0.62, 0.22, 1)
    b.inputs["Emission Strength"].default_value = 40.0
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=16, radius1=15.0, radius2=0.0, depth=95)
    bmesh.ops.rotate(bm, verts=bm.verts[:], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'Y'))
    bmesh.ops.translate(bm, verts=bm.verts[:], vec=(47.5, 0, 0))
    pontas = []
    for i in range(20):
        r = 48.0 if i % 2 == 0 else 10.0
        a = 2 * math.pi * i / 20
        pontas.append((r * math.cos(a), r * math.sin(a)))
    frente = [bm.verts.new((3.0, y, z)) for y, z in pontas]
    tras = [bm.verts.new((1.0, y, z)) for y, z in pontas]
    bm.faces.new(frente)
    bm.faces.new(tras)
    for i in range(20):
        j = (i + 1) % 20
        bm.faces.new([frente[i], frente[j], tras[j], tras[i]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    ob = objeto("clarao", bm, mat)
    ob.location = (X_BOCA + 0.4, 0, 0)
    P["clarao"] = ob


# ---------------------------------------------------------------- animações

# onde cada faixa começa na linha do tempo do .blend (30 qps) e quantos quadros ela tem
REPOUSO_INICIO, REPOUSO_FIM = 1, 2
TIRO_INICIO, TIRO_FIM = 5, 3
REC_INICIO, REC_FIM = 12, 110
RECUO = (-185.0, 0.0, -105.0)          # onde a mão segura (no punho): o coice gira a arma em volta daqui
TAMPA_ABERTA = math.radians(72)        # a tampa gira na dobradiça da frente e levanta atrás
GATILHO_PUXADO = math.radians(14)
CURSO_MANEJO = 118.0
EVENTOS = {"tiro": {"disparo": 1},
           "recarregar": {"tampa_abre": 13, "pente_sai": 25, "troca": 45, "pente_entra": 66, "tampa_fecha": 75,
                          "ferrolho": 88}}
VISTAS_ANIMACAO = {}


def animar(P):
    """Pivôs, hierarquia e as faixas: repouso, tiro (3 quadros, o mod repete em rajada) e recarregar (abre a
    tampa, tira a caixa vazia, põe a nova passando a fita na bandeja, fecha a tampa e puxa o manejo)."""
    cena = bpy.context.scene
    cena.render.fps = 30
    _pivo(P["gatilho"], PIVO_GATILHO)
    _pivo(P["tampa"], PIVO_TAMPA)
    _pivo(P["ferrolho"], (-16.0, -40.0, 5.0))
    raiz = bpy.data.objects.new(RAIZ, None)
    raiz.empty_display_size = 60
    cena.collection.objects.link(raiz)
    raiz.location = RECUO
    bpy.context.view_layer.update()
    for nome, ob in P.items():
        if nome not in ("estojo_topo", "bala_topo"):
            _prender(ob, raiz)
    bpy.context.view_layer.update()
    for nome in ("estojo_topo", "bala_topo"):
        _prender(P[nome], P["pente"])
    bpy.context.view_layer.update()
    P["clarao"].scale = (0, 0, 0)
    P["estojo_ejetado"].scale = (0, 0, 0)

    fer, gat, tampa, pente, flash, ejet = (P[n] for n in ("ferrolho", "gatilho", "tampa", "pente", "clarao",
                                                          "estojo_ejetado"))
    animados = [raiz, fer, gat, tampa, pente, flash, ejet]
    repouso = {ob: {"location": tuple(ob.location), "rotation_euler": tuple(ob.rotation_euler),
                    "scale": tuple(ob.scale)} for ob in animados}
    loc0 = {ob: Vector(repouso[ob]["location"]) for ob in animados}
    R = math.radians

    base = Faixa("repouso", REPOUSO_INICIO, REPOUSO_FIM, 'HOLD')
    for ob in animados:
        for prop, valor in repouso[ob].items():
            base.k(ob, prop, 1, valor)
            base.k(ob, prop, REPOUSO_FIM, valor)
    base.gravar(repouso)

    # tiro: quadro 1 é o disparo (clarão cheio, gatilho puxado, coice), quadro 2 o clarão girado e menor com o
    # estojo saindo por baixo, quadro 3 a arma de volta ao repouso com o estojo caindo. Repetido, vira a rajada.
    t = Faixa("tiro", TIRO_INICIO, TIRO_FIM)
    for q, a in [(1, GATILHO_PUXADO), (2, GATILHO_PUXADO), (3, 0)]:
        t.k(gat, "rotation_euler", q, (0, a, 0), 'CONSTANT')
    for q, esc, giro in [(1, 1.0, 0.0), (2, 0.6, 0.7), (3, 0.0, 0.0)]:
        t.k(flash, "scale", q, (esc * 1.15, esc, esc), 'CONSTANT')
        t.k(flash, "rotation_euler", q, (giro, 0, 0), 'CONSTANT')
    c = loc0[ejet]
    for q, esc, d, rot in [(1, 0, (0, 0, 0), (0, 0, 0)), (2, 1, (-50, -16, -66), (0.2, 0, -0.3)),
                           (3, 1, (-56, -30, -124), (1.3, 0.5, -1.6))]:
        t.k(ejet, "scale", q, (esc, esc, esc), 'CONSTANT')
        t.k(ejet, "location", q, c + Vector(d), 'CONSTANT')
        t.k(ejet, "rotation_euler", q, rot, 'CONSTANT')
    for q, giro, desl in [(1, -1.6, (-5, 0, 1.2)), (2, -0.7, (-2.2, 0, 0.5)), (3, 0, (0, 0, 0))]:
        t.k(raiz, "rotation_euler", q, (0, R(giro), 0), 'LINEAR')
        t.k(raiz, "location", q, loc0[raiz] + Vector(desl), 'LINEAR')
    t.gravar(repouso)
    VISTAS_ANIMACAO["anim-tiro"] = TIRO_INICIO + 1

    r = Faixa("recarregar", REC_INICIO, REC_FIM)
    deitada = ((R(24), 0, R(-6)), loc0[raiz] + Vector((0, 0, 18)))
    for q, (rot, loc) in [(1, ((0, 0, 0), loc0[raiz])), (10, deitada), (100, deitada), (110, ((0, 0, 0), loc0[raiz]))]:
        r.k(raiz, "rotation_euler", q, rot)
        r.k(raiz, "location", q, loc)
    for q, a in [(1, 0), (12, 0), (20, TAMPA_ABERTA), (68, TAMPA_ABERTA), (75, 0)]:
        r.k(tampa, "rotation_euler", q, (0, a, 0))
    p0 = loc0[pente]
    # a fita sai pela janela da esquerda (a caixa anda para a esquerda), a caixa cai e some; a nova sobe longe da
    # arma, chega à altura certa do lado de fora e entra de lado, deitando a fita na bandeja
    for q, d, rot, interp in [(1, (0, 0, 0), (0, 0, 0), 'BEZIER'), (24, (0, 0, 0), (0, 0, 0), 'BEZIER'),
                              (32, (0, 74, 0), (0, 0, 0), 'BEZIER'), (42, (0, 150, -150), (0.5, 0.15, 0.3), 'CONSTANT'),
                              (48, (0, 150, -160), (0.35, 0, 0.25), 'BEZIER'), (58, (0, 74, 0), (0, 0, 0), 'BEZIER'),
                              (66, (0, 0, 0), (0, 0, 0), 'BEZIER')]:
        r.k(pente, "location", q, p0 + Vector(d), interp)
        r.k(pente, "rotation_euler", q, rot, interp)
    for q, esc in [(42, 1), (43, 0), (47, 0), (48, 1)]:
        r.k(pente, "scale", q, (esc, esc, esc), 'CONSTANT')
    for q, d in [(1, 0), (80, 0), (88, -CURSO_MANEJO), (91, -CURSO_MANEJO), (98, 0)]:
        r.k(fer, "location", q, loc0[fer] + Vector((d, 0, 0)))
    r.gravar(repouso)
    VISTAS_ANIMACAO["anim-recarga"] = REC_INICIO + 61

    cena.frame_start, cena.frame_end = 1, REC_INICIO + REC_FIM + 3
    for nome, quadro in [("repouso", REPOUSO_INICIO), ("tiro", TIRO_INICIO), ("recarregar", REC_INICIO)]:
        cena.timeline_markers.new(nome, frame=quadro)
    cena.frame_set(0)
    pecas = ["ferrolho", "gatilho", "tampa", "pente", "estojo_topo", "bala_topo", "clarao", "estojo_ejetado"]
    dados = {"raiz": RAIZ, "fps": 30,
             "faixas": {"repouso": {"inicio": REPOUSO_INICIO, "quadros": REPOUSO_FIM, "eventos": {}},
                        "tiro": {"inicio": TIRO_INICIO, "quadros": TIRO_FIM, "eventos": EVENTOS["tiro"]},
                        "recarregar": {"inicio": REC_INICIO, "quadros": REC_FIM, "eventos": EVENTOS["recarregar"]}},
             "pecas": pecas}
    SAIDA.mkdir(exist_ok=True)
    (SAIDA / "animacoes.json").write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return raiz


def conferir_movimento(P):
    """Mede, em momentos das animações, quantos triângulos de cada par de peças se cruzam, comparado com o
    repouso: número que cresce muito é peça atravessando outra."""
    from mathutils.bvhtree import BVHTree
    cena = bpy.context.scene
    pares = [("ferrolho", "armacao"), ("ferrolho", "empunhadura"), ("gatilho", "caixa_gatilho"),
             ("gatilho", "guarda_mato"), ("tampa", "armacao"), ("tampa", "alca"), ("tampa", "bandeja"),
             ("tampa", "estojo_topo"), ("tampa", "bala_topo"), ("tampa", "pente"), ("pente", "armacao"),
             ("pente", "encaixe"), ("pente", "bandeja"), ("pente", "guarda_mato"), ("pente", "empunhadura"),
             ("pente", "caixa_gatilho"), ("pente", "bipe"), ("estojo_topo", "armacao"), ("bala_topo", "armacao"),
             ("estojo_topo", "bandeja"), ("estojo_ejetado", "armacao"), ("estojo_ejetado", "pente"),
             ("estojo_ejetado", "caixa_gatilho"), ("estojo_ejetado", "encaixe")]
    momentos = [("tiro, disparo", TIRO_INICIO), ("tiro, estojo saindo", TIRO_INICIO + 1),
                ("tiro, estojo caindo", TIRO_INICIO + 2), ("recarga, tampa aberta", REC_INICIO + 21),
                ("recarga, fita saindo", REC_INICIO + 27), ("recarga, caixa caindo", REC_INICIO + 36),
                ("recarga, caixa nova subindo", REC_INICIO + 53), ("recarga, fita entrando", REC_INICIO + 61),
                ("recarga, tampa fechando", REC_INICIO + 71), ("recarga, manejo atrás", REC_INICIO + 87)]

    def arvore(ob):
        dg = bpy.context.evaluated_depsgraph_get()
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ev.matrix_world
        t = BVHTree.FromPolygons([mw @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
        ev.to_mesh_clear()
        return t

    def contar():
        arvores = {}
        for a, b in pares:
            for n in (a, b):
                if n not in arvores:
                    arvores[n] = arvore(P[n])
        return {(a, b): len(arvores[a].overlap(arvores[b])) for a, b in pares}

    cena.frame_set(0)
    base = contar()
    linhas = ["", "Animações (30 qps): " + ", ".join(f"{n} {i} a {i + q - 1}" for n, i, q in [
        ("repouso", REPOUSO_INICIO, REPOUSO_FIM), ("tiro", TIRO_INICIO, TIRO_FIM), ("recarregar", REC_INICIO, REC_FIM)]),
              "Eventos (quadro contado do começo da faixa): " + "; ".join(
                  f"{f}: " + ", ".join(f"{e} {q}" for e, q in ev.items()) for f, ev in EVENTOS.items()),
              "Cruzamentos entre peças (triângulos que se tocam; repouso -> no momento):"]
    for nome, quadro in momentos:
        cena.frame_set(quadro)
        agora = contar()
        mudou = [f"{a} x {b}: {base[(a, b)]} -> {agora[(a, b)]}" for a, b in pares
                 if agora[(a, b)] > base[(a, b)] + 10]
        linhas.append(f"  {nome} (quadro {quadro}): " + ("; ".join(mudou) if mudou else "nada novo"))
    cena.frame_set(0)
    linhas.append("No repouso: " + "; ".join(f"{a} x {b}: {n}" for (a, b), n in base.items() if n))
    return linhas


def relatorio(P, extra=()):
    linhas = ["METRALHADORA 3D: relatório", ""]
    todos_x, todos_y, todos_z = [], [], []
    tris_total = 0
    abertas = []
    for nome, ob in P.items():
        if ob.matrix_world.to_scale().length < 1e-6:
            continue
        cs = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        x0, x1 = min(c.x for c in cs), max(c.x for c in cs)
        y0, y1 = min(c.y for c in cs), max(c.y for c in cs)
        z0, z1 = min(c.z for c in cs), max(c.z for c in cs)
        todos_x += [x0, x1]
        todos_y += [y0, y1]
        todos_z += [z0, z1]
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        abertas_ob = sum(1 for e in bm.edges if len(e.link_faces) != 2)
        tris = sum(len(f.verts) - 2 for f in bm.faces)
        bm.free()
        tris_total += tris
        if abertas_ob:
            abertas.append(nome)
        linhas.append(f"{nome:<22} {x1 - x0:7.1f} x {y1 - y0:5.1f} x {z1 - z0:6.1f} mm  {tris:6d} triângulos"
                      f"  {'MALHA ABERTA: ' + str(abertas_ob) + ' arestas' if abertas_ob else 'fechada'}")
    linhas += ["", f"Total: {len(P)} peças, {tris_total} triângulos (sem contar as escondidas)",
               f"Comprimento {max(todos_x) - min(todos_x):.0f} mm, altura {max(todos_z) - min(todos_z):.0f} mm "
               f"(da alça de transporte ao fundo da caixa de munição), largura {max(todos_y) - min(todos_y):.0f} mm",
               "Sem textura: tudo é cor lisa.",
               "As peças se sobrepõem de propósito nas junções: cada uma é um sólido fechado, não uma malha única."]
    linhas += list(extra)
    if abertas:
        linhas.append("ATENÇÃO, malha aberta em: " + ", ".join(abertas))
    for aviso in AVISOS:
        linhas.append("ATENÇÃO, " + aviso)
    texto = "\n".join(linhas)
    (SAIDA / "relatorio.txt").write_text(texto, encoding="utf-8")
    print(texto)


# ---------------------------------------------------------------- imagens

def renderizar():
    leve = "--leve" in ARGS
    vistas_leves = ("lateral-direita", "tres-quartos", "anim-tiro", "anim-recarga")
    if "--vistas" in ARGS:
        vistas_leves = tuple(ARGS[ARGS.index("--vistas") + 1].split(","))
    rapido = "--rapido" in ARGS or leve
    cena = bpy.context.scene
    if leve:
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            k32.SetPriorityClass(k32.GetCurrentProcess(), 0x40)   # IDLE_PRIORITY_CLASS
        except Exception:
            pass
        cena.render.threads_mode = 'FIXED'
        cena.render.threads = 4
    cena.unit_settings.system = 'METRIC'
    cena.unit_settings.scale_length = 0.001
    cena.render.engine = 'CYCLES'
    cena.cycles.device = 'CPU'
    cena.cycles.samples = 16 if leve else (24 if rapido else 256)
    cena.cycles.use_denoising = True
    cena.cycles.denoiser = 'OPENIMAGEDENOISE'
    cena.render.resolution_x, cena.render.resolution_y = 1920, 1200
    cena.render.resolution_percentage = 50 if rapido else 100
    cena.view_settings.view_transform = 'AgX'
    cena.view_settings.look = 'None'

    mundo = bpy.data.worlds.new("mundo")
    mundo.use_nodes = True
    mundo.node_tree.nodes["Background"].inputs["Color"].default_value = (0.12, 0.12, 0.125, 1)
    cena.world = mundo

    chao = -420.0
    perfil = [(chao, 0), (chao, 2600)]
    for i in range(1, 13):
        a = math.radians(90 * i / 12)
        perfil.append((chao + 1200 - 1200 * math.cos(a), 2600 + 1200 * math.sin(a)))
    perfil += [(8000, 3800), (8000, 0)]
    fundo = tornear("fundo", perfil, material("fundo", (0.36, 0.355, 0.35), rug=0.8), eixo='z', seg=128)
    acabar(fundo, angulo=60)

    alvo = (-20, 0, -50)
    luz_de_estudio("luz_topo", (0, 0, 1500), alvo, (1100, 500), 2.0)
    luz_de_estudio("luz_principal", (-700, -1600, 800), alvo, (700, 450), 6.0)
    luz_de_estudio("luz_faixa", (200, -800, 1250), (0, 0, -10), (1300, 90), 13)
    luz_de_estudio("luz_contra", (1000, 1200, 330), alvo, (450, 650), 7.0)
    luz_de_estudio("luz_recorte", (-1400, 950, 150), alvo, (380, 600), 5.0)
    luz_de_estudio("luz_baixa", (550, -1250, -200), alvo, (600, 180), 2.0)

    cam_ob = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
    cam_ob.data.clip_start, cam_ob.data.clip_end = 10, 30000
    cena.collection.objects.link(cam_ob)
    cena.camera = cam_ob
    mira = bpy.data.objects.new("mira_camera", None)
    cena.collection.objects.link(mira)
    trava = cam_ob.constraints.new('TRACK_TO')
    trava.target = mira
    trava.track_axis = 'TRACK_NEGATIVE_Z'
    trava.up_axis = 'UP_Y'

    RENDER.mkdir(exist_ok=True)
    for velho in RENDER.glob("*.png"):
        velho.unlink()

    def foto(nome, local, ponto, lente, f=None, foco=None, quadro=0):
        if leve and nome not in vistas_leves:
            return
        cena.frame_set(quadro)
        cam_ob.location = local
        mira.location = ponto
        cam_ob.data.lens = lente
        cam_ob.data.dof.use_dof = f is not None
        if f is not None:
            cam_ob.data.dof.aperture_fstop = f
            cam_ob.data.dof.focus_distance = (Vector(local) - Vector(foco or ponto)).length
        cena.render.filepath = str(RENDER / f"{nome}.png")
        bpy.ops.render.render(write_still=True)

    foto("lateral-direita", (-15, -2300, -40), (-15, 0, -45), 65)
    foto("lateral-esquerda", (-15, 2300, -40), (-15, 0, -45), 65)
    foto("tres-quartos", (1000, -1350, 520), (-30, 0, -40), 45)
    foto("traseira-esquerda", (-1100, 1250, 520), (0, 0, -40), 45)
    foto("boca", (900, -380, 160), (420, 0, 0), 85, f=5.6, foco=(X_BOCA, 0, 0))
    foto("anim-tiro", (-15, -2300, -40), (-15, 0, -45), 65, quadro=VISTAS_ANIMACAO["anim-tiro"])
    foto("anim-recarga", (450, 1500, 650), (-60, 0, -40), 45, quadro=VISTAS_ANIMACAO["anim-recarga"])
    cena.frame_set(0)
    cena.unit_settings.scale_length = 1.0


# ---------------------------------------------------------------- exportação

def exportar(raiz):
    SAIDA.mkdir(exist_ok=True)
    cena = bpy.context.scene
    cena.frame_set(0)
    bpy.context.preferences.filepaths.save_version = 0
    for ob in bpy.data.objects:
        ob.select_set(False)
    bpy.ops.wm.save_as_mainfile(filepath=str(SAIDA / f"{RAIZ}.blend"))
    # OBJ em milímetros, parado e carregado, sem o clarão nem o estojo que cai (escondidos)
    for velho in SAIDA.glob(f"{RAIZ}.obj*"):
        velho.unlink()
    for ob in bpy.data.objects:
        ob.select_set(ob.type == 'MESH' and ob.name not in ("clarao", "estojo_ejetado"))
    bpy.ops.wm.obj_export(filepath=str(SAIDA / f"{RAIZ}.obj"), export_materials=True, path_mode='COPY',
                          forward_axis='NEGATIVE_Z', up_axis='Y', apply_modifiers=True,
                          export_selected_objects=True)
    # GLB em metros, com uma animação por faixa, todas começando no zero
    for ob in bpy.data.objects:
        if ob.animation_data:
            for trilha in ob.animation_data.nla_tracks:
                for faixa in trilha.strips:
                    faixa.frame_start_ui = 1
    escala = bpy.data.objects.new("escala_metros", None)
    cena.collection.objects.link(escala)
    escala.scale = (0.001, 0.001, 0.001)
    raiz.parent = escala
    bpy.context.view_layer.update()
    bpy.ops.export_scene.gltf(filepath=str(SAIDA / f"{RAIZ}.glb"), export_format='GLB', use_selection=False,
                              export_apply=True, export_animations=True, export_animation_mode='NLA_TRACKS')


def principal():
    P = construir()
    raiz = animar(P)
    relatorio(P, conferir_movimento(P))
    if "--sem-render" not in ARGS:
        renderizar()
        for o in list(bpy.data.objects):
            if o.name.startswith(("luz_", "fundo", "camera", "mira_camera")):
                bpy.data.objects.remove(o)
    exportar(raiz)
    print("pronto")


principal()
