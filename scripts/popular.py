"""Independent unrestricted Steam CN top sellers, including full-price games."""
import os
import hot_low

if __name__=="__main__":
    hot_low.OUTPUT=hot_low.DATA/"popular.json"
    hot_low.collect(max_checked=int(os.environ.get("HOT_MAX_CHECKED","100")),unrestricted=True)
