# frozen_string_literal: true
#
# Batch language classifier using the linguist pinned inside vendor/source_snapshot.
#
#   LINGUIST_LIB=/path/to/lib ruby linguist_classify.rb jobs.jsonl results.jsonl
#
# Each line of jobs.jsonl is {"id": String, "v": [[variant, filesystem_path, logical_path], ...]}.
# The filesystem path supplies the bytes; the logical path is what linguist sees, so the
# caller can hold the path constant across variants and vary only the content.
#
# One line of linguist.rb is dropped at load time: `require 'linguist/repository'`.
# That file exists to classify whole Git repositories and drags in the native `rugged`
# gem; nothing in the single-blob detection path uses it. No detection logic is edited.

require "json"
require "digest/sha2"

LIB = ENV.fetch("LINGUIST_LIB") { abort "LINGUIST_LIB must point at the copied linguist lib/" }
$LOAD_PATH.unshift(LIB)

original = File.read(File.join(LIB, "linguist.rb"))
kept = original.lines.reject { |l| l =~ /^require ['"]linguist\/repository['"]\s*$/ }
dropped = original.lines.count - kept.count
abort "expected to drop exactly 1 require, dropped #{dropped}" unless dropped == 1
STDERR.puts "linguist.rb: #{original.lines.count} lineas -> #{kept.count} (excluida: require 'linguist/repository')"
patched = File.join(LIB, "linguist_no_repo.rb")
File.write(patched, kept.join)
require "linguist_no_repo"
require "linguist/blob"

# Captures which strategy produced each answer, through linguist's own instrumenter hook.
class StrategyRecorder
  attr_accessor :last

  def instrument(name, payload = {})
    value = block_given? ? yield : nil
    @last = payload[:strategy].to_s if name == "linguist.detected" && payload[:strategy]
    value
  end
end

RECORDER = StrategyRecorder.new
Linguist.instrumenter = RECORDER

def describe(blob)
  RECORDER.last = nil
  language = blob.language
  {
    "language"      => language && language.name,
    "type"          => language && language.type.to_s,
    "group"         => language && language.group,
    "strategy"      => RECORDER.last || "bail_out",
    "generated"     => !!blob.generated?,
    "documentation" => !!blob.documentation?,
    "vendored"      => !!blob.vendored?,
    "binary"        => !!blob.binary?,
    "likely_binary" => !!blob.likely_binary?,
    "empty"         => !!blob.empty?,
    "bytes"         => blob.size,
    "sha256"        => Digest::SHA256.hexdigest(blob.data.to_s),
  }
rescue StandardError => e
  { "error" => "#{e.class}: #{e.message}" }
end

jobs_path, results_path = ARGV
abort "usage: linguist_classify.rb jobs.jsonl results.jsonl" if jobs_path.nil? || results_path.nil?

t0 = Time.now
done = 0
File.open(results_path, "w") do |out|
  File.foreach(jobs_path) do |line|
    next if line.strip.empty?

    job = JSON.parse(line)
    variants = {}
    job["v"].each do |(name, fs_path, logical_path)|
      content = if fs_path == "-"
                  ""
                else
                  File.binread(fs_path)
                end
      variants[name] = describe(Linguist::Blob.new(logical_path, content))
    end
    out.puts(JSON.generate({ "id" => job["id"], "v" => variants }))
    done += 1
    STDERR.puts "clasificados #{done} (#{(Time.now - t0).round(1)}s)" if (done % 200).zero?
  end
end
STDERR.puts "total jobs=#{done} wall=#{(Time.now - t0).round(2)}s"
