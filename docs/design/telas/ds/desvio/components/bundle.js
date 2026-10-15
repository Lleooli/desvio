/* @ds-bundle: {"format":4,"namespace":"Desvio","components":[{"name":"Ceu"},{"name":"Estrada"},{"name":"Destaque"},{"name":"Button"},{"name":"Segmented"},{"name":"Chip"},{"name":"Rating"},{"name":"SwipeCard"},{"name":"SwipeActions"},{"name":"Toast"},{"name":"JanelaCidade"},{"name":"StopItem"},{"name":"TextField"},{"name":"BottomNav"},{"name":"Icon"}]} */
(function () {
  var React = window.React, h = React.createElement;

  function cx() { return Array.prototype.filter.call(arguments, Boolean).join(" "); }
  function rest(props, omit) {
    var o = {};
    for (var k in props) if (Object.prototype.hasOwnProperty.call(props, k) && omit.indexOf(k) < 0) o[k] = props[k];
    return o;
  }
  function numero(n, casas) {
    return Number(n).toLocaleString("pt-BR", { minimumFractionDigits: casas || 0, maximumFractionDigits: casas || 0 });
  }

  /* Ícones de traço, grade de 24px, traço 1.8. Desenhados para este sistema. */
  var PATHS = {
    x: "M6 6l12 12M18 6L6 18",
    check: "M5 12.5l4.5 4.5L19 7",
    star: "M12 3.5l2.6 5.3 5.9.9-4.25 4.15 1 5.85L12 16.9l-5.25 2.8 1-5.85L3.5 9.7l5.9-.9z",
    pin: "M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0113 0c0 5.4-6.5 11-6.5 11zM12 12.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5z",
    camera: "M4 8h3l2-2.5h6L17 8h3v11H4zM12 16.5a3.5 3.5 0 100-7 3.5 3.5 0 000 7z",
    food: "M7 3v8M5 3v5a2 2 0 004 0V3M7 11v10M16 21V3c-2 1.5-3 4-3 7v3h3",
    fuel: "M4 20V5a1 1 0 011-1h8a1 1 0 011 1v15M3 20h12M6 8h6M14 9h2.5a1.5 1.5 0 011.5 1.5V16a1.5 1.5 0 003 0V8l-3-3",
    leaf: "M5 19c0-8 5-14 14-14 0 9-6 14-14 14zM5 19l7-7",
    bed: "M3 18V7M3 13h18v5M21 13a3 3 0 00-3-3h-7v3M7 11.5a1.5 1.5 0 100-3 1.5 1.5 0 000 3z",
    route: "M6 19a2 2 0 100-4 2 2 0 000 4zM18 9a2 2 0 100-4 2 2 0 000 4zM6 15V9.5A3.5 3.5 0 019.5 6H12M18 9v5.5a3.5 3.5 0 01-3.5 3.5H12",
    compass: "M12 21a9 9 0 100-18 9 9 0 000 18zM15.5 8.5l-2 5-5 2 2-5z",
    user: "M12 12a4 4 0 100-8 4 4 0 000 8zM4 20a8 8 0 0116 0",
    suitcase: "M4 8h16v11H4zM9 8V5.5A1.5 1.5 0 0110.5 4h3A1.5 1.5 0 0115 5.5V8M4 13h16",
    clock: "M12 21a9 9 0 100-18 9 9 0 000 18zM12 7v5l3 2",
    at: "M16 12a4 4 0 10-1.2 2.85M16 8v5a2.5 2.5 0 005 0v-1a9 9 0 10-3.5 7.1",
    plane: "M10.5 13.5L3 11l1.5-1.5 8 1L16.5 6a1.8 1.8 0 012.5 2.5L14.5 12.5l1 8L14 22l-2.5-7.5L8 17.5V20l-1.5 1.5-1-3-3-1L4 16h2.5z",
    car: "M5 16v3M19 16v3M3 16h18v-4l-2-5H5l-2 5zM3 12h18M7 14h1M16 14h1"
  };

  function Icon(p) {
    var s = p.size || 20;
    return h("svg", {
      className: cx("dv-icon", p.className), width: s, height: s, viewBox: "0 0 24 24",
      fill: p.filled ? "currentColor" : "none", stroke: "currentColor", strokeWidth: p.strokeWidth || 1.8,
      strokeLinecap: "round", strokeLinejoin: "round",
      role: p.label ? "img" : undefined, "aria-label": p.label, "aria-hidden": p.label ? undefined : true
    }, h("path", { d: PATHS[p.name] || "" }));
  }

  var CATEGORIAS = {
    turismo: { label: "Turismo", icon: "camera" },
    restaurante: { label: "Restaurante", icon: "food" },
    posto: { label: "Posto", icon: "fuel" },
    natureza: { label: "Natureza", icon: "leaf" },
    hospedagem: { label: "Hospedagem", icon: "bed" }
  };

  function Button(p) {
    var variant = p.variant || "primary", size = p.size || "md";
    return h("button", Object.assign({ type: "button" }, rest(p, ["variant", "size", "icon", "block", "className", "children"]), {
      className: cx("dv-btn", "dv-btn--" + variant, size === "sm" && "dv-btn--sm", p.block && "dv-btn--block", p.className)
    }), p.icon ? h(Icon, { name: p.icon, size: size === "sm" ? 18 : 20 }) : null, p.children);
  }

  function Chip(p) {
    var cat = CATEGORIAS[p.categoria] || {};
    var label = p.children || p.label || cat.label;
    var icon = p.icon || cat.icon;
    var conteudo = [icon ? h(Icon, { key: "i", name: icon, size: 16 }) : null, h("span", { key: "t" }, label)];
    var cls = cx("dv-chip", p.onPhoto && "dv-chip--onphoto", p.className);
    if (p.onClick) {
      return h("button", { type: "button", className: cls, "aria-pressed": !!p.selected, onClick: p.onClick }, conteudo);
    }
    return h("span", { className: cls }, conteudo);
  }

  function Rating(p) {
    if (p.nota == null) return null;
    var texto = numero(p.nota, 1);
    var aval = p.avaliacoes != null ? numero(p.avaliacoes) : null;
    return h("span", {
      className: cx("dv-rating", p.onPhoto && "dv-rating--onphoto", p.className),
      "aria-label": "Nota " + texto + (aval ? ", " + aval + " avaliações" : "")
    },
      h(Icon, { name: "star", size: 16, filled: true }),
      h("b", null, texto),
      aval ? h("span", null, "(" + aval + ")") : null
    );
  }

  function handleDe(url) {
    if (!url) return null;
    var m = /instagram\.com\/([A-Za-z0-9_.]+)/.exec(url);
    return m ? m[1] : String(url).replace(/^@/, "");
  }

  function SwipeCard(p) {
    var handle = handleDe(p.instagram);
    var stampTexto = { bora: "Bora", passo: "Passo", favorito: "Favorito" }[p.stamp];
    return h("article", { className: cx("dv-card", p.className), style: p.style, "aria-label": p.nome },
      p.foto ? h("img", { className: "dv-card__media", src: p.foto, alt: "", draggable: false })
        : h("div", { className: "dv-card__semfoto dv-ceu" + (p.categoria === "natureza" || p.categoria === "posto" ? " dv-ceu--placa" : ""), "aria-hidden": true },
            h(Icon, { name: (CATEGORIAS[p.categoria] || {}).icon || "pin", size: 72, strokeWidth: 1.4 })),
      h("div", { className: "dv-card__scrim", "aria-hidden": true }),
      h("div", { className: "dv-card__top" },
        p.categoria ? h(Chip, { categoria: p.categoria, onPhoto: true }) : h("span"),
        p.km != null ? h("span", { className: "dv-km" }, "KM " + numero(p.km), p.horas != null ? h("small", null, "+" + numero(p.horas, p.horas % 1 ? 1 : 0) + "H") : null) : null
      ),
      stampTexto ? h("span", { className: "dv-stamp dv-stamp--" + p.stamp, role: "status" }, stampTexto) : null,
      h("div", { className: "dv-card__body" },
        h("h2", { className: "dv-card__name" }, p.nome),
        h("div", { className: "dv-card__meta" },
          p.cidade ? h("span", { className: "dv-card__place" }, h(Icon, { name: "pin", size: 16 }), p.cidade + (p.uf ? ", " + p.uf : "")) : null,
          h(Rating, { nota: p.nota, avaliacoes: p.avaliacoes, onPhoto: true })
        ),
        p.descricao ? h("p", { className: "dv-card__desc" }, p.descricao) : null,
        handle ? h("a", { className: "dv-card__ig", href: "https://instagram.com/" + handle, target: "_blank", rel: "noopener" },
          h(Icon, { name: "at", size: 16 }), handle,
          p.instagramProvavel ? h("em", null, " · provável") : null) : null
      )
    );
  }

  function SwipeActions(p) {
    function item(tipo, icone, rotulo, fn, extra) {
      return h("div", { className: "dv-act__item", key: tipo },
        h("button", Object.assign({ type: "button", className: "dv-act__btn dv-act__btn--" + tipo, onClick: fn, disabled: p.disabled, "aria-label": rotulo }, extra || {}),
          h(Icon, { name: icone, size: tipo === "favorito" ? 22 : 28, strokeWidth: 2.4, filled: tipo === "favorito" })),
        h("span", { "aria-hidden": true }, rotulo));
    }
    return h("div", { className: cx("dv-act", p.className), role: "group", "aria-label": "Decidir sobre este lugar" },
      item("passo", "x", "Passo", p.onPasso),
      item("favorito", "star", "Favorito", p.onFavorito),
      item("bora", "check", "Bora", p.onBora));
  }

  function StopItem(p) {
    var tipo = p.tipo || "parada";
    var sub = [];
    if (p.horas != null) sub.push(p.horas === 0 ? "Saída" : "~" + numero(p.horas, p.horas % 1 ? 1 : 0) + "h de estrada");
    if (p.dias) sub.push(p.dias + (p.dias > 1 ? " dias" : " dia"));
    return h("div", { className: cx("dv-stop", "dv-stop--" + tipo, p.ativo && "dv-stop--ativo", p.className), "aria-current": p.ativo ? "step" : undefined },
      h("span", { className: "dv-stop__km" }, p.km != null ? "KM " + numero(p.km) : ""),
      h("span", { className: "dv-stop__rail", "aria-hidden": true }, h("span", { className: "dv-stop__dot" })),
      h("div", { className: "dv-stop__info" },
        h("p", { className: "dv-stop__city" }, p.cidade + (p.uf ? ", " + p.uf : "")),
        sub.length ? h("p", { className: "dv-stop__sub" }, sub.join(" · ")) : null),
      p.total != null ? h("span", { className: "dv-stop__count" }, (p.aceitos || 0) + " de " + p.total) : h("span"));
  }

  var _id = 0;
  function TextField(p) {
    var idRef = React.useRef(null);
    if (!idRef.current) idRef.current = p.id || "dv-field-" + (++_id);
    var id = idRef.current;
    return h("div", { className: cx("dv-field", p.erro && "dv-field--erro", p.className) },
      p.label ? h("label", { className: "dv-field__label", htmlFor: id }, p.label) : null,
      h("div", { className: "dv-field__box" },
        p.icon ? h(Icon, { name: p.icon, size: 20 }) : null,
        h("input", Object.assign({ id: id, className: "dv-field__input", "aria-invalid": !!p.erro, "aria-describedby": (p.erro || p.hint) ? id + "-hint" : undefined },
          rest(p, ["label", "icon", "hint", "erro", "className", "id"])))),
      (p.erro || p.hint) ? h("span", { className: "dv-field__hint", id: id + "-hint" }, p.erro || p.hint) : null);
  }

  var NAV = [
    { id: "viagens", label: "Viagens", icon: "suitcase" },
    { id: "descobrir", label: "Descobrir", icon: "compass" },
    { id: "roteiro", label: "Roteiro", icon: "route" },
    { id: "perfil", label: "Perfil", icon: "user" }
  ];
  function BottomNav(p) {
    var ativo = p.ativo || "descobrir";
    return h("nav", { className: cx("dv-nav", p.className), "aria-label": "Navegação principal" },
      NAV.map(function (it) {
        var atual = it.id === ativo;
        return h("button", { key: it.id, type: "button", className: "dv-nav__item", "aria-current": atual ? "page" : undefined,
          onClick: p.onChange ? function () { p.onChange(it.id); } : undefined },
          h("span", { className: "dv-nav__pill" }, h(Icon, { name: it.icon, size: 22, strokeWidth: atual ? 2.2 : 1.8 })),
          it.label);
      }));
  }

  /* Destaque: marca-texto amarelo atrás de uma palavra de título */
  function Destaque(p) { return h("span", { className: cx("dv-destaque", p.className) }, p.children); }

  /* Ceu: fundo de amanhecer feito só com as cores da marca */
  function Ceu(p) {
    var style = Object.assign({}, p.style || {});
    if (p.fundoSerra) style["--fundo-serra"] = p.fundoSerra;
    return h("div", {
      className: cx("dv-ceu", p.variante === "placa" && "dv-ceu--placa", p.serra && "dv-ceu--serra", p.arredondado && "dv-ceu--arredondado", p.className),
      style: style
    }, h("div", { className: "dv-ceu__conteudo" }, p.children));
  }

  /* Estrada: pista curva com os nomes das cidades correndo por ela */
  var CAMINHOS = {
    curva: "M-30 150 C 60 150 90 58 190 66 S 310 168 430 104",
    subida: "M-30 182 C 90 176 130 120 210 110 S 330 60 430 26"
  };
  var _estrada = 0;
  function Estrada(p) {
    var cidades = p.cidades || [];
    var sep = "   ·   ";
    var unidade = cidades.join(sep) + sep;
    var vezes = 6;
    var idRef = React.useRef(null);
    if (!idRef.current) idRef.current = "dv-estrada-" + (++_estrada);
    var textoRef = React.useRef(null);
    var largura = p.largura || 46;
    React.useEffect(function () {
      var el = textoRef.current;
      if (!el || p.parado) return undefined;
      if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return undefined;
      var tp = el.querySelector("textPath");
      var ciclo = el.getComputedTextLength() / vezes;
      if (!ciclo) return undefined;
      var vel = p.velocidade || 36, off = 0, ultimo = null, raf;
      function passo(t) {
        if (ultimo != null) {
          off -= ((t - ultimo) / 1000) * vel;
          if (off <= -ciclo) off += ciclo;
        }
        ultimo = t;
        tp.setAttribute("startOffset", off.toFixed(2));
        raf = window.requestAnimationFrame(passo);
      }
      raf = window.requestAnimationFrame(passo);
      return function () { window.cancelAnimationFrame(raf); };
    }, [unidade, p.velocidade, p.parado]);
    var d = CAMINHOS[p.variante] || CAMINHOS.curva;
    return h("svg", {
      className: cx("dv-estrada", p.className), viewBox: "0 0 400 200", role: "img",
      "aria-label": p.rotulo || ("Rota: " + cidades.join(", "))
    },
      h("path", { id: idRef.current, d: d, fill: "none" }),
      h("use", { href: "#" + idRef.current, className: "dv-estrada__borda", strokeWidth: largura + 6 }),
      h("use", { href: "#" + idRef.current, className: "dv-estrada__pista", strokeWidth: largura }),
      h("text", { ref: textoRef, className: "dv-estrada__texto", "aria-hidden": true },
        h("textPath", { href: "#" + idRef.current, startOffset: 0 }, Array(vezes + 1).join(unidade))));
  }

  /* Segmented: escolha entre 2 a 4 opções exclusivas (Carro / Avião) */
  function Segmented(p) {
    var opcoes = p.opcoes || [];
    var interno = React.useState(p.padrao != null ? p.padrao : (opcoes[0] || {}).valor);
    var valor = p.valor != null ? p.valor : interno[0];
    function escolher(v) { if (p.valor == null) interno[1](v); if (p.onChange) p.onChange(v); }
    return h("div", { className: cx("dv-seg", p.block && "dv-seg--block", p.className), role: "radiogroup", "aria-label": p.rotulo },
      opcoes.map(function (o) {
        var ativo = o.valor === valor;
        return h("button", { key: o.valor, type: "button", role: "radio", "aria-checked": ativo, tabIndex: ativo ? 0 : -1,
          className: "dv-seg__opt", onClick: function () { escolher(o.valor); } },
          o.icon ? h(Icon, { name: o.icon, size: 20 }) : null, o.label);
      }));
  }

  /* Toast: confirmação curta depois de uma ação, com desfazer */
  function Toast(p) {
    return h("div", { className: cx("dv-toast", p.className), role: "status" },
      h(Icon, { name: p.icon || "check", size: 20, strokeWidth: 2.2 }),
      h("span", null, p.children),
      p.acao ? h("button", { type: "button", className: "dv-toast__acao", onClick: p.onAcao }, p.acao) : null);
  }

  /* JanelaCidade: miniatura de cidade em formato de janelinha de avião */
  function JanelaCidade(p) {
    var dias = p.dias != null ? p.dias + (p.dias === 1 ? " dia" : " dias") : null;
    return h("button", { type: "button", className: cx("dv-janela", p.className), "aria-pressed": p.selecionada ? true : undefined, onClick: p.onClick },
      h("span", { className: "dv-janela__moldura" },
        h("span", { className: "dv-janela__vidro" },
          p.foto ? h("img", { src: p.foto, alt: "" }) : h("span", { className: "dv-ceu" + (p.variante === "placa" ? " dv-ceu--placa" : "") }),
          dias ? h("span", { className: "dv-janela__dias" }, dias) : null)),
      h("span", null,
        h("p", { className: "dv-janela__nome" }, p.cidade),
        p.uf ? h("p", { className: "dv-janela__uf" }, p.uf) : null));
  }

  window.Desvio = Object.assign(window.Desvio || {}, {
    Ceu: Ceu, Estrada: Estrada, Destaque: Destaque, Button: Button, Segmented: Segmented, Chip: Chip, Rating: Rating,
    SwipeCard: SwipeCard, SwipeActions: SwipeActions, Toast: Toast, JanelaCidade: JanelaCidade,
    StopItem: StopItem, TextField: TextField, BottomNav: BottomNav, Icon: Icon, CATEGORIAS: CATEGORIAS
  });
})();
