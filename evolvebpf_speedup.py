import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

mpl.rcParams.update({
    "font.size": 15,
    "axes.labelsize": 17,
    "xtick.labelsize": 14,
    "ytick.labelsize": 14,
    "legend.fontsize": 14,
})

hooks=["merge_bio","io_start","io_done","vfs_read","vfs_write","tcp_state"]

orig=np.array([1984.78,11404.25,2949.54,1973.42,1471.86,680.13])
aggr=np.array([878.56,4246.82,2697.18,1034.60,811.48,424.23])
cons=np.array([1405.57,6919.76,2832.11,1717.05,1380.81,596.36])

speedup_cons=orig/cons
speedup_aggr=orig/aggr

# x=np.array([0,1,2,3.5,4.5,6],dtype=float)
x = np.array([0, 0.9, 1.8,
              3.0, 3.9,
              5.1],dtype=float)
w=0.42

fig,ax=plt.subplots(figsize=(6.8,4.4))
b1=ax.bar(x-w/2,speedup_cons,width=w,label="Naive",
          hatch="///", edgecolor="black", linewidth=0.8)
b2=ax.bar(x+w/2,speedup_aggr,width=w,label="Aggressive",
          edgecolor="black", linewidth=0.8)

ax.axhline(1.0,ls="--",lw=1)
ax.set_ylabel("Speedup")
ax.set_xticks(x)
ax.set_xticklabels(hooks, rotation=25, ha="right", fontsize=14)
ax.set_ylim(0.8,2.8)

for bars in (b1,b2):
    for b in bars:
        h=b.get_height()
        ax.text(b.get_x()+b.get_width()/2,h+0.04,f"{h:.1f}×",
                ha="center",fontsize=9, fontweight="bold")

ax.legend(frameon=False, ncol=1, loc="upper right",
          bbox_to_anchor=(0.98, 0.98), borderaxespad=0.0)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
plt.tight_layout(pad=1.0, rect=[0, 0, 1, 0.92])

# Save as vector PDF
plt.savefig(
    "evolvebpf_speedup.pdf",
    format="pdf",
    bbox_inches="tight"
)
