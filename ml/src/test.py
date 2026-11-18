from preprocess import preprocess_report_image

out = preprocess_report_image("test.jpg", device="cuda")
print("tensor:", out["tensor"].shape, out["tensor"].device, out["tensor"].dtype)
print("range:", out["tensor"].min().item(), out["tensor"].max().item())
print("original_shape:", out["original_shape"])
print("scale_ratio:", out["scale_ratio"])
print("padding (left, top):", out["padding"])