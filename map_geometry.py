"""Geometry of the Conquest world map (pure Python, no Streamlit).

The map is generated, not hand drawn:
  1. 14 "continent" territories come from a weighted Voronoi diagram (power
     diagram) of seed points inside an ellipse. Bigger weight = bigger region.
  2. Every border is cut into small steps and bent by a smooth noise function
     of the POSITION, so two neighbours always get the exact same border and the
     coast becomes irregular (bays and peninsulas).
  3. Two small island territories are added, linked to the mainland by sea lanes.
  4. Mountains, forests, hills and rivers are placed deterministically.

Everything is computed once at import time. The rest of the app only reads:
    MAP        geometry + decorations (sent to the map component)
    NEIGHBORS  {territory_id: [neighbor ids]}  (also used by game_logic)

Territory ids are the index in SEEDS (0-13), then the islands (14, 15). They must
match the order of TERRITORY_DEFS in game_logic.py.
"""

import math
import random

CENTER_X, CENTER_Y = 550, 345
RADIUS_X, RADIUS_Y = 410, 255          # the continent starts as this ellipse

# (x, y, weight) for ids 0-13. Weight > 0 makes a region larger.
SEEDS = [
    (240, 225, 5000),   # 0  north-west
    (395, 170, 2000),   # 1  north
    (565, 150, 0),      # 2  north (mountains)
    (735, 175, 2500),   # 3  north-east
    (880, 285, 0),      # 4  east
    (205, 350, -1500),  # 5  west coast
    (355, 315, 0),      # 6  west-center
    (545, 290, 9000),   # 7  center (largest)
    (715, 330, 0),      # 8  center-east
    (840, 445, 0),      # 9  south-east
    (265, 475, 0),      # 10 south-west
    (430, 455, 0),      # 11 south
    (590, 470, 3000),   # 12 south-center
    (735, 525, 0),      # 13 south coast
]
# Islands: ids 14 and 15 -> (center x, center y, radius, shape seed)
ISLANDS = [(150, 118, 52, 1.3), (962, 592, 54, 4.1)]
# Sea lanes between an island and mainland territories.
SEA_LINKS = [(14, 0), (14, 5), (15, 9), (15, 13)]

# Decoration style per territory (flavor only): forest / mountain / hills / plain
TERRAIN = {
    0: "hills", 1: "forest", 2: "mountain", 3: "forest", 4: "mountain",
    5: "hills", 6: "plain", 7: "forest", 8: "plain", 9: "hills",
    10: "plain", 11: "forest", 12: "forest", 13: "hills",
    14: "mountain", 15: "mountain",
}
# Rivers: (start territory, end angle in degrees on the coast)
RIVERS = [(2, -100), (4, 20), (7, 160)]

# Noise phases. Checked so that no territory outline crosses itself; if you change
# the seeds or the noise, re-check this (a spike or loop on the coast means a fold).
NOISE_PHASE_X, NOISE_PHASE_Y = 4.0, 0.5
EDGE_STEP = 9           # px between points when bending borders
MIN_BORDER = 6          # shorter shared edges do not count as neighbors


# ----------------------------------------------------------------------
# Smooth noise (a function of position, so shared borders stay shared)
# ----------------------------------------------------------------------
def _wave(x, y, freq, phase):
    return (math.sin(freq * (x * 0.86 + y * 0.51) + phase)
            + math.sin(freq * (-x * 0.45 + y * 0.89) + phase * 1.7))


def _smoothstep(a, b, t):
    t = max(0.0, min(1.0, (t - a) / (b - a)))
    return t * t * (3 - 2 * t)


def _displace(x, y):
    """Return the displaced position of a border point."""
    radial = math.hypot((x - CENTER_X) / RADIUS_X, (y - CENTER_Y) / RADIUS_Y)
    coast = _smoothstep(0.80, 1.0, radial)
    inner = 20.0 + 38.0 * coast
    octaves = [(0.0115, 1.0), (0.027, 0.7), (0.058, 0.42), (0.105, 0.22)]
    total = sum(a for _, a in octaves) * 2
    dx = sum(a * _wave(x, y, f, NOISE_PHASE_X) for f, a in octaves) / total
    dy = sum(a * _wave(x, y, f, NOISE_PHASE_Y) for f, a in octaves) / total
    return x + dx * inner * 1.8, y + dy * inner * 1.8


# ----------------------------------------------------------------------
# Voronoi cells by half-plane clipping
# ----------------------------------------------------------------------
def _clip(poly, a, b, c, tag):
    """Keep the part of poly with a*x + b*y <= c.

    poly is a list of (x, y, tag) where tag labels the edge that starts at
    that vertex. New edges created by the cut get `tag` (the neighbor id).
    """
    out = []
    count = len(poly)
    for i in range(count):
        px, py, ptag = poly[i]
        qx, qy, _ = poly[(i + 1) % count]
        fp = a * px + b * py - c
        fq = a * qx + b * qy - c
        if fp <= 0:
            out.append((px, py, ptag))
            if fq > 0:                      # leaving: add the cut point
                t = fp / (fp - fq)
                out.append((px + (qx - px) * t, py + (qy - py) * t, tag))
        elif fq <= 0:                       # entering: add the cut point
            t = fp / (fp - fq)
            out.append((px + (qx - px) * t, py + (qy - py) * t, ptag))
    return out


def _voronoi_cell(index):
    xi, yi, wi = SEEDS[index]
    ellipse = [
        (CENTER_X + RADIUS_X * math.cos(2 * math.pi * k / 72),
         CENTER_Y + RADIUS_Y * math.sin(2 * math.pi * k / 72), -1)
        for k in range(72)
    ]
    poly = ellipse
    for j, (xj, yj, wj) in enumerate(SEEDS):
        if j != index:
            a, b = 2 * (xj - xi), 2 * (yj - yi)
            c = xj * xj + yj * yj - xi * xi - yi * yi + wi - wj
            poly = _clip(poly, a, b, c, j)
    return poly


def _edge_points(p, q):
    """Points along edge p->q. Order-independent so neighbors agree exactly."""
    first, second = (p, q) if (round(p[0], 2), round(p[1], 2)) <= (round(q[0], 2), round(q[1], 2)) else (q, p)
    steps = max(1, int(math.hypot(second[0] - first[0], second[1] - first[1]) / EDGE_STEP))
    points = [(first[0] + (second[0] - first[0]) * k / steps,
               first[1] + (second[1] - first[1]) * k / steps) for k in range(steps + 1)]
    if first is not p:
        points.reverse()
    return points


def _bent_outline(cell):
    """Turn a straight-edged cell into a list of bent (x, y) points."""
    outline = []
    for i, (x, y, _) in enumerate(cell):
        nx, ny, _ = cell[(i + 1) % len(cell)]
        for point in _edge_points((x, y), (nx, ny))[:-1]:
            outline.append(_displace(*point))
    return outline


# ----------------------------------------------------------------------
# Small geometry helpers
# ----------------------------------------------------------------------
def _path(points):
    return "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in points) + "Z"


def _centroid(points):
    area = cx = cy = 0.0
    for i, (x0, y0) in enumerate(points):
        x1, y1 = points[(i + 1) % len(points)]
        cross = x0 * y1 - x1 * y0
        area += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if abs(area) < 1e-6:
        return points[0]
    return cx / (3 * area), cy / (3 * area)


def _inside(points, x, y):
    result = False
    j = len(points) - 1
    for i in range(len(points)):
        xi, yi = points[i]
        xj, yj = points[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            result = not result
        j = i
    return result


def _island_outline(cx, cy, radius, seed):
    points = []
    for k in range(72):
        angle = 2 * math.pi * k / 72
        r = radius * (1 + 0.22 * math.sin(3 * angle + seed) + 0.12 * math.sin(5 * angle + 2 * seed)
                      + 0.05 * math.sin(11 * angle + seed))
        points.append((cx + r * math.cos(angle), cy + 0.8 * r * math.sin(angle)))
    return points


# ----------------------------------------------------------------------
# Decorations
# ----------------------------------------------------------------------
def _decorate(territory_id, outline, cx, cy):
    """Mountains, trees and hills inside a territory, away from its label."""
    rng = random.Random(1000 + territory_id)
    kind = TERRAIN.get(territory_id, "plain")
    wanted = {"mountain": ("mountains", 6), "forest": ("trees", 11),
              "hills": ("hills", 4), "plain": ("hills", 2)}[kind]
    xs = [p[0] for p in outline]
    ys = [p[1] for p in outline]
    placed = []
    result = {"mountains": [], "trees": [], "hills": []}
    margin = 14

    def free(x, y, spacing):
        corners = [(x + dx, y + dy) for dx in (-margin, margin) for dy in (-margin, margin)]
        if not all(_inside(outline, px, py) for px, py in corners):
            return False
        if abs(x - cx) < 64 and -40 < y - cy < 36:      # keep the label readable
            return False
        return all(math.hypot(x - ox, y - oy) > spacing for ox, oy in placed)

    for key, count in (wanted, ("trees", 3) if kind in ("hills", "plain") else ("hills", 2)):
        tries = 0
        while len(result[key]) < count and tries < 300:
            tries += 1
            x, y = rng.uniform(min(xs), max(xs)), rng.uniform(min(ys), max(ys))
            spacing = 20 if key == "trees" else 38
            if free(x, y, spacing):
                size = rng.uniform(13, 20) if key == "mountains" else rng.uniform(4, 6.5) if key == "trees" else rng.uniform(10, 16)
                result[key].append([round(x, 1), round(y, 1), round(size, 1)])
                placed.append((x, y))
    return result


def _river(start_point, angle_deg, land_points):
    """A meandering line from start_point to the coast (clipped to land later)."""
    sx, sy = start_point
    angle = math.radians(angle_deg)
    ex = CENTER_X + RADIUS_X * 1.1 * math.cos(angle)
    ey = CENTER_Y + RADIUS_Y * 1.1 * math.sin(angle)
    length = math.hypot(ex - sx, ey - sy)
    nx, ny = -(ey - sy) / length, (ex - sx) / length
    points = []
    steps = int(length / 10)
    for k in range(steps + 1):
        t = k / steps
        wobble = 16 * math.sin(t * 9 + angle) * math.sin(t * math.pi) + 6 * math.sin(t * 23)
        points.append((sx + (ex - sx) * t + nx * wobble, sy + (ey - sy) * t + ny * wobble))
    return "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in points)


# ----------------------------------------------------------------------
# Build the map
# ----------------------------------------------------------------------
def _build():
    territories = []
    neighbors = {i: set() for i in range(len(SEEDS) + len(ISLANDS))}
    outlines = {}

    for i in range(len(SEEDS)):
        cell = _voronoi_cell(i)
        for k, (x, y, tag) in enumerate(cell):                # shared borders -> neighbors
            nx, ny, _ = cell[(k + 1) % len(cell)]
            if tag >= 0 and math.hypot(nx - x, ny - y) > MIN_BORDER:
                neighbors[i].add(tag)
                neighbors[tag].add(i)
        outlines[i] = _bent_outline(cell)

    for offset, (ix, iy, radius, seed) in enumerate(ISLANDS):
        outlines[len(SEEDS) + offset] = _island_outline(ix, iy, radius, seed)
    for a, b in SEA_LINKS:
        neighbors[a].add(b)
        neighbors[b].add(a)

    centers = {}
    for i, outline in outlines.items():
        cx, cy = _centroid(outline)
        centers[i] = (cx, cy)
        territories.append({
            "id": i,
            "d": _path(outline),
            "cx": round(cx, 1), "cy": round(cy, 1),
            "island": i >= len(SEEDS),
            "decor": _decorate(i, outline, cx, cy),
        })

    rivers = []
    for start_id, angle in RIVERS:
        mountains = territories[start_id]["decor"]["mountains"]
        start = tuple(mountains[0][:2]) if mountains else centers[start_id]
        rivers.append(_river(start, angle, outlines[start_id]))

    # View box = bounding box of all land plus a margin of open sea
    all_points = [p for outline in outlines.values() for p in outline]
    margin = 55
    vx = math.floor(min(p[0] for p in all_points) - margin)
    vy = math.floor(min(p[1] for p in all_points) - margin)
    vw = math.ceil(max(p[0] for p in all_points) + margin) - vx
    vh = math.ceil(max(p[1] for p in all_points) + margin) - vy

    rng = random.Random(7)
    waves = []
    while len(waves) < 40:
        x, y = rng.uniform(vx + 20, vx + vw - 20), rng.uniform(vy + 20, vy + vh - 20)
        far_from_continent = math.hypot((x - CENTER_X) / RADIUS_X, (y - CENTER_Y) / RADIUS_Y) > 1.22
        far_from_islands = all(math.hypot(x - ix, y - iy) > r + 40 for ix, iy, r, _ in ISLANDS)
        if far_from_continent and far_from_islands:
            waves.append([round(x), round(y)])

    sea_links = [[round(centers[a][0]), round(centers[a][1]), round(centers[b][0]), round(centers[b][1])]
                 for a, b in SEA_LINKS]
    return {
        "viewBox": [vx, vy, vw, vh],
        "territories": territories, "rivers": rivers,
        "waves": waves, "seaLinks": sea_links,
    }, {i: sorted(n) for i, n in neighbors.items()}


MAP, NEIGHBORS = _build()
