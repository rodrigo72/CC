// Bytefield - generate protocol headers and more
// Feel free to contribute with any features you think are missing.
// Still a WIP - alpha stage and a bit hacky at the moment

#import "@preview/tablex:0.0.4": tablex, cellx, gridx
#set text(font: "IBM Plex Mono")

#let bfcell(
  len, // lenght of the fields in bits 
  content, 
  fill: none, // color to fill the field
  height: auto, // height of the field
) = cellx(colspan: len, fill: fill, inset: 0pt)[#box(height: height, width: 100%, stroke: (dash: "densely-dotted", thickness: 0.75pt))[#content]]


#let bytefield(
  bits: 32, 
  rowheight: 2em, 
  bitheader: auto,   
  msb_first: false,
  ..fields
) = {
  // state variables
  let col_count = 0
  let cells = ()

  // calculate cells
  for (idx, field) in fields.pos().enumerate() {
    let (size, content, fill, ..) = field;
    let remaining_cols = bits - col_count;
    col_count = calc.rem(col_count + size, bits);
    // if no size was specified
    if size == none {
      size = remaining_cols
      content = content + sym.star
    }
    if size > bits and remaining_cols == bits and calc.rem(size, bits) == 0 {
      content = content + " (" + str(size) + " Bit)"
      cells.push(bfcell(int(bits),fill:fill, height: rowheight * size/bits)[#content])
      size = 0
    }

    while size > 0 {
      let width = calc.min(size, remaining_cols);
      size -= remaining_cols
      remaining_cols = bits
      cells.push(bfcell(int(width),fill:fill, height: rowheight,)[#content])
    }
  
  }


  bitheader = if bitheader == auto { 
    range(bits).map(i => if calc.rem(i,8) == 0 or i == (bits - 1) { 
      text(9pt)[#i]
      } else { none })
  } else if bitheader == "all" {
    range(bits).map(i => text(9pt)[#i])
  } else if bitheader != none {
    assert(type(bitheader) == array, message: "header must be an array, none or 'all' ")
    range(bits).map(i => if i in bitheader { text(9pt)[#i] } else {none})
  }

  if(msb_first == true) {
    bitheader = bitheader.rev()
  }

  
  box(width: 100%)[
    #gridx(
      columns: range(bits).map(i => 1fr),
      align: center + horizon,
      ..bitheader,
      ..cells,
    )
  ]
}

// Low level API
#let bitbox(length_in_bits, content, fill: none) = (
  type: "bitbox",
  size: length_in_bits,   // length of the field 
  fill: fill,
  content: content,
  var: false, 
  show_size: false,
)

// High level API
#let bit(..args) = bitbox(1, ..args)
#let bits(len, ..args) = bitbox(len, ..args)
#let byte(..args) = bitbox(8, ..args)
#let bytes(len, ..args) = bitbox(len * 8, ..args)
#let padding(..args) = bitbox(none, ..args)

// Rotating text for flags
#let flagtext(text) = align(center,rotate(270deg,text))