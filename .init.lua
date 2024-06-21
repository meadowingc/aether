-- special script called by main redbean process at startup
ProgramBrand("aether")

require("fennel").install().dofile("src/main.fnl")