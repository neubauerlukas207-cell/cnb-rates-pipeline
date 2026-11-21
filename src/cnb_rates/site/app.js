// Dashboard kurzů ČNB – čte data.json vygenerovaný pipeline, bez knihoven.

const $ = (sel) => document.querySelector(sel)
const nf = (digits) => new Intl.NumberFormat('cs-CZ', { minimumFractionDigits: digits, maximumFractionDigits: digits })
const df = new Intl.DateTimeFormat('cs-CZ', { day: 'numeric', month: 'numeric', year: 'numeric' })
const parseDay = (iso) => new Date(`${iso}T00:00:00`)

/** Desetinná místa podle velikosti kurzu (JPY 0,14031, IDR 0,00122, EUR 24,470). */
const formatRate = (v) => nf(v < 0.01 ? 6 : v < 1 ? 5 : 3).format(v)

function formatPct(v) {
  if (v === null || v === undefined) return '–'
  return `${v > 0 ? '+' : ''}${nf(2).format(v)} %`
}

const trendClass = (v) => (v > 0 ? 'up' : v < 0 ? 'down' : '')

const state = { data: null, code: 'EUR', days: 90, sortKey: null, sortDir: 1 }

async function load() {
  const res = await fetch('data.json', { cache: 'no-cache' })
  if (!res.ok) throw new Error(`data.json: HTTP ${res.status}`)
  return res.json()
}

function renderMeta(data) {
  $('#meta').textContent = `Kurzovní lístek ze dne ${df.format(parseDay(data.latest_day))} · ${data.currencies.length} měn`
}

function renderCards(data) {
  $('#cards').replaceChildren(
    ...data.currencies.slice(0, 4).map((c) => {
      const card = document.createElement('button')
      card.type = 'button'
      card.className = 'card'
      card.dataset.code = c.code
      card.innerHTML = `
        <span class="code">${c.code}</span>
        <span class="value">${formatRate(c.latest)} Kč</span>
        <span class="change ${trendClass(c.change_1d_pct)}">${formatPct(c.change_1d_pct)} za den</span>`
      card.addEventListener('click', () => selectCurrency(c.code))
      return card
    }),
  )
}

function fillSelects(data) {
  for (const id of ['#currency', '#conv-currency']) {
    $(id).replaceChildren(...data.currencies.map((c) => new Option(c.code, c.code)))
  }
  $('#currency').value = state.code
  $('#conv-currency').value = state.code
}

// --- graf (SVG) --------------------------------------------------------------------------------

function renderChart() {
  const currency = state.data.currencies.find((c) => c.code === state.code)
  const points = currency.history.slice(-state.days)
  const svg = $('#chart')
  const width = svg.clientWidth || 800
  const height = svg.clientHeight || 320
  const pad = { top: 16, right: 16, bottom: 28, left: 64 }
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`)

  const values = points.map(([, v]) => v)
  let min = Math.min(...values)
  let max = Math.max(...values)
  if (min === max) {
    min -= 1
    max += 1
  }
  const margin = (max - min) * 0.08
  min -= margin
  max += margin

  const x = (i) => pad.left + (i / Math.max(1, points.length - 1)) * (width - pad.left - pad.right)
  const y = (v) => pad.top + (1 - (v - min) / (max - min)) * (height - pad.top - pad.bottom)

  const path = points.map(([, v], i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('')
  const area = `${path}L${x(points.length - 1).toFixed(1)},${height - pad.bottom}L${x(0).toFixed(1)},${height - pad.bottom}Z`

  const ticks = 4
  const grid = Array.from({ length: ticks + 1 }, (_, i) => {
    const v = min + ((max - min) * i) / ticks
    return `<line class="grid" x1="${pad.left}" x2="${width - pad.right}" y1="${y(v)}" y2="${y(v)}"/>
            <text class="axis" x="${pad.left - 8}" y="${y(v) + 4}" text-anchor="end">${formatRate(v)}</text>`
  }).join('')
  const first = points[0][0]
  const last = points[points.length - 1][0]

  svg.innerHTML = `
    ${grid}
    <path class="area" d="${area}"/>
    <path class="line" d="${path}"/>
    <text class="axis" x="${pad.left}" y="${height - 8}">${df.format(parseDay(first))}</text>
    <text class="axis" x="${width - pad.right}" y="${height - 8}" text-anchor="end">${df.format(parseDay(last))}</text>
    <line id="cursor" class="cursor" y1="${pad.top}" y2="${height - pad.bottom}" visibility="hidden"/>
    <circle id="dot" class="dot" r="4" visibility="hidden"/>`

  $('#chart-title').textContent = `Vývoj kurzu ${state.code}`
  svg.dataset.points = String(points.length)

  // tooltip: nejbližší bod k myši
  svg.onpointermove = (e) => {
    const rect = svg.getBoundingClientRect()
    const px = ((e.clientX - rect.left) / rect.width) * width
    const i = Math.round(((px - pad.left) / (width - pad.left - pad.right)) * (points.length - 1))
    if (i < 0 || i >= points.length) return
    const [day, v] = points[i]
    const cx = x(i)
    const cy = y(v)
    $('#cursor').setAttribute('x1', cx)
    $('#cursor').setAttribute('x2', cx)
    $('#cursor').setAttribute('visibility', 'visible')
    $('#dot').setAttribute('cx', cx)
    $('#dot').setAttribute('cy', cy)
    $('#dot').setAttribute('visibility', 'visible')
    const tip = $('#tooltip')
    tip.hidden = false
    tip.textContent = `${df.format(parseDay(day))}: ${formatRate(v)} Kč`
    tip.style.left = `${(cx / width) * rect.width}px`
    tip.style.top = `${(cy / height) * rect.height}px`
  }
  svg.onpointerleave = () => {
    $('#tooltip').hidden = true
    $('#cursor').setAttribute('visibility', 'hidden')
    $('#dot').setAttribute('visibility', 'hidden')
  }
}

// --- tabulka -----------------------------------------------------------------------------------

function renderTable() {
  const rows = [...state.data.currencies]
  if (state.sortKey) {
    rows.sort((a, b) => {
      const av = a[state.sortKey] ?? -Infinity
      const bv = b[state.sortKey] ?? -Infinity
      return (typeof av === 'string' ? av.localeCompare(bv) : av - bv) * state.sortDir
    })
  }
  $('#table tbody').replaceChildren(
    ...rows.map((c) => {
      const tr = document.createElement('tr')
      tr.dataset.code = c.code
      tr.innerHTML = `
        <th scope="row"><button type="button" class="link">${c.code}</button></th>
        <td class="num">${formatRate(c.latest)}</td>
        <td class="num ${trendClass(c.change_1d_pct)}">${formatPct(c.change_1d_pct)}</td>
        <td class="num ${trendClass(c.change_30d_pct)}">${formatPct(c.change_30d_pct)}</td>
        <td class="num ${trendClass(c.change_ytd_pct)}">${formatPct(c.change_ytd_pct)}</td>
        <td class="num">${c.volatility_30d_pct === null ? '–' : `${nf(1).format(c.volatility_30d_pct)} %`}</td>
        <td class="num">${formatRate(c.min_1y)} – ${formatRate(c.max_1y)}</td>`
      tr.querySelector('button').addEventListener('click', () => {
        selectCurrency(c.code)
        $('#chart').scrollIntoView({ behavior: 'smooth', block: 'center' })
      })
      return tr
    }),
  )
  for (const th of document.querySelectorAll('#table th[data-key]')) {
    th.setAttribute('aria-sort', th.dataset.key === state.sortKey ? (state.sortDir > 0 ? 'ascending' : 'descending') : 'none')
  }
}

// --- převodník ---------------------------------------------------------------------------------

function renderConverter() {
  const amount = Number($('#conv-amount').value)
  const currency = state.data.currencies.find((c) => c.code === $('#conv-currency').value)
  if (!currency || !Number.isFinite(amount) || amount < 0) {
    $('#conv-result').textContent = '–'
    return
  }
  $('#conv-result').textContent = `${nf(2).format(amount)} ${currency.code} = ${nf(2).format(amount * currency.latest)} Kč`
}

function selectCurrency(code) {
  state.code = code
  $('#currency').value = code
  renderChart()
}

async function main() {
  try {
    state.data = await load()
  } catch (e) {
    $('#meta').textContent = 'Data se nepodařilo načíst.'
    console.error(e)
    return
  }
  if (!state.data.currencies.some((c) => c.code === state.code)) state.code = state.data.currencies[0].code
  renderMeta(state.data)
  renderCards(state.data)
  fillSelects(state.data)
  renderChart()
  renderTable()
  renderConverter()

  $('#currency').addEventListener('change', (e) => selectCurrency(e.target.value))
  for (const button of document.querySelectorAll('.range button')) {
    button.addEventListener('click', () => {
      state.days = Number(button.dataset.days)
      for (const b of document.querySelectorAll('.range button')) b.setAttribute('aria-pressed', String(b === button))
      renderChart()
    })
  }
  for (const th of document.querySelectorAll('#table th[data-key]')) {
    th.addEventListener('click', () => {
      state.sortDir = state.sortKey === th.dataset.key ? -state.sortDir : 1
      state.sortKey = th.dataset.key
      renderTable()
    })
  }
  $('#conv-amount').addEventListener('input', renderConverter)
  $('#conv-currency').addEventListener('change', renderConverter)
  window.addEventListener('resize', renderChart)
}

main()
