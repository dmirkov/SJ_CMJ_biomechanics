import pandas as pd
import numpy as np
import scipy
import matplotlib.pyplot as plt

print("\n" + "="*30)
print("✅ SISTEM JE SPREMAN ZA RAD!")
print(f"Pandas verzija: {pd.__version__}")
print(f"NumPy verzija:  {np.__version__}")
print("="*30 + "\n")

# Mali test generisanja signala
x = np.linspace(0, 10, 100)
y = np.sin(x)
print("Test obrade signala: USPEŠAN")