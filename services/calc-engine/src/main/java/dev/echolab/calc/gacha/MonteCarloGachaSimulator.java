package dev.echolab.calc.gacha;

import java.util.ArrayList;
import java.util.List;
import java.util.SplittableRandom;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.stream.IntStream;

/**
 * ピックアップ獲得確率のモンテカルロ法。
 *
 * <p>試行をチャンクに分け、チャンクごとに {@code seed} から決まる乱数列を使う。 そのため 3 つの実行方式（逐次・parallel stream・仮想スレッド）は 同じ seed
 * なら完全に同じ結果を返す。方式の違いは速度だけで、JMH で比較する。
 */
public final class MonteCarloGachaSimulator {

  /** 実行方式。 */
  public enum Mode {
    SEQUENTIAL,
    PARALLEL_STREAM,
    VIRTUAL_THREADS
  }

  /** 1 チャンクあたりの試行数。 */
  static final int CHUNK_SIZE = 10_000;

  /** {@code pulls} 回以内にピックアップを獲得する確率の推定値。 */
  public double probabilityWithin(
      PityRules rules, GachaState start, int pulls, int trials, long seed, Mode mode) {
    if (trials <= 0) {
      throw new IllegalArgumentException("trials は 1 以上である必要があります: " + trials);
    }
    if (pulls < 0) {
      throw new IllegalArgumentException("pulls は 0 以上である必要があります: " + pulls);
    }
    start.requireValidFor(rules);
    int chunks = (trials + CHUNK_SIZE - 1) / CHUNK_SIZE;
    long successes =
        switch (mode) {
          case SEQUENTIAL ->
              IntStream.range(0, chunks)
                  .mapToLong(i -> runChunk(rules, start, pulls, trials, seed, i))
                  .sum();
          case PARALLEL_STREAM ->
              IntStream.range(0, chunks)
                  .parallel()
                  .mapToLong(i -> runChunk(rules, start, pulls, trials, seed, i))
                  .sum();
          case VIRTUAL_THREADS -> runOnVirtualThreads(rules, start, pulls, trials, seed, chunks);
        };
    return (double) successes / trials;
  }

  private static long runOnVirtualThreads(
      PityRules rules, GachaState start, int pulls, int trials, long seed, int chunks) {
    try (ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor()) {
      List<Future<Long>> futures = new ArrayList<>(chunks);
      for (int i = 0; i < chunks; i++) {
        int chunk = i;
        futures.add(executor.submit(() -> runChunk(rules, start, pulls, trials, seed, chunk)));
      }
      long total = 0;
      for (Future<Long> f : futures) {
        total += f.get();
      }
      return total;
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
      throw new IllegalStateException("シミュレーションが中断されました", e);
    } catch (ExecutionException e) {
      throw new IllegalStateException("シミュレーションに失敗しました", e.getCause());
    }
  }

  private static long runChunk(
      PityRules rules, GachaState start, int pulls, int trials, long seed, int chunk) {
    SplittableRandom random = new SplittableRandom(chunkSeed(seed, chunk));
    int from = chunk * CHUNK_SIZE;
    int count = Math.min(CHUNK_SIZE, trials - from);
    long successes = 0;
    for (int t = 0; t < count; t++) {
      if (simulateOne(rules, start, pulls, random)) {
        successes++;
      }
    }
    return successes;
  }

  /** チャンク番号から乱数の種を作る（SplitMix64 の混合関数）。 */
  static long chunkSeed(long seed, int chunk) {
    long z = seed + 0x9E3779B97F4A7C15L * (chunk + 1L);
    z = (z ^ (z >>> 30)) * 0xBF58476D1CE4E5B9L;
    z = (z ^ (z >>> 27)) * 0x94D049BB133111EBL;
    return z ^ (z >>> 31);
  }

  private static boolean simulateOne(
      PityRules rules, GachaState start, int pulls, SplittableRandom random) {
    int pity = start.pity();
    boolean guaranteed = start.guaranteed();
    for (int n = 0; n < pulls; n++) {
      double q = rules.fiveStarRate(pity + 1);
      if (random.nextDouble() < q) {
        if (guaranteed || random.nextDouble() < rules.featuredRate()) {
          return true;
        }
        guaranteed = rules.guaranteeAfterLoss();
        pity = 0;
      } else {
        pity++;
      }
    }
    return false;
  }
}
