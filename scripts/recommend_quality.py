"""Transparent quality adjustment using review sample size.

A high positive percentage from only a few ratings should not outrank a
well-established game without a confidence penalty. This is a ranking
adjustment, not a hard restriction, especially for exploration games.
"""
import math

def review_confidence(total,prior=500):
    n=max(0,int(total or 0))
    return round(n/(n+prior),4)

def quality_adjustment(pct,total):
    if pct is None:return 0.0
    p=max(0,min(100,float(pct)))/100
    strength=review_confidence(total)
    # Neutral 75% prior. Maximum shift of 0.75 points.
    estimated=.75+(p-.75)*strength
    return round(max(-.75,min(.75,(estimated-p)*3.0)),3)

def rank_recommendation(game):
    score=float(game.get("recommend_score") or 0)
    adjustment=quality_adjustment(game.get("review_pct"),game.get("review_count"))
    return round(score+adjustment,3)
