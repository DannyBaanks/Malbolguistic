# frozen_string_literal: true
#
# Serializa la base de datos del clasificador de linguist, igual que la tarea
# `:samples` del Rakefile del snapshot:
#   File.write 'lib/linguist/samples_data.rb',
#     "#frozen_string_literal: true\nDATA = #{PP.pp(Linguist::Samples.data, +'')}"
#
#   ruby -I<lib> linguist_gen_samples.rb <out.rb>

require "linguist/samples"
require "pp"

abort "usage: linguist_gen_samples.rb OUT" if ARGV.empty?
data = Linguist::Samples.data
File.write(ARGV[0], "#frozen_string_literal: true\nDATA = " + PP.pp(data, +""))
STDERR.puts "samples_data.rb escrito: #{File.size(ARGV[0])} bytes"
