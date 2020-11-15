From root directory
`pybabel extract . -o bot\locale\messages.pot`
`pybabel update -i bot\locale\messages.pot -d bot\locale`
`pybabel init -i bot\locale\messages.pot -l {langauge} -d bot\locale`
`pybabel compile -d bot\locale\`