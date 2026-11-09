// Writes the facts graph/code_graph.py reads, one tab-separated row each:
//   METHOD  file  fullName  line  name
//   CFG|CDG file  fullName  <node>  <node>
//   DDG     file  fullName  <node>  <node>  variable
//   RAISE   file  fullName  call id  inside a try
//   END                                      (last row; PrintWriter hides write errors, so a file without it is incomplete)
// <node> is: id  label  line  code.
import io.shiftleft.semanticcpg.language._
import io.shiftleft.codepropertygraph.generated.nodes.{CfgNode, ControlStructure, Method, StoredNode}

@main def exec(cpgFile: String, outFile: String) = {
  importCpg(cpgFile)
  val out = new java.io.PrintWriter(outFile, "UTF-8")
  def clean(s: String) = s.replace("\t", " ").replace("\r", " ").replace("\n", " ").take(60)
  def show(n: StoredNode): String = n match {
    case c: CfgNode => s"${c.id}\t${c.label}\t${c.lineNumber.getOrElse(-1)}\t${clean(c.code)}"
    case o => s"${o.id}\t${o.label}\t-1\t"
  }
  def owner(c: CfgNode): (String, String) = c match {
    case m: Method => (m.filename, m.fullName)
    case other => scala.util.Try((other.method.filename, other.method.fullName)).getOrElse(("?", "?"))
  }
  cpg.method.foreach { m => out.print(s"METHOD\t${m.filename}\t${m.fullName}\t${m.lineNumber.getOrElse(-1)}\t${m.name}\n") }
  cpg.all.collect { case c: CfgNode => c }.foreach { src =>
    val (file, method) = owner(src)
    src._cfgOut.foreach { dst => out.print(s"CFG\t$file\t$method\t${show(src)}\t${show(dst)}\n") }
    src._cdgOut.foreach { dst => out.print(s"CDG\t$file\t$method\t${show(src)}\t${show(dst)}\n") }
    src.outE("REACHING_DEF").foreach { e => out.print(s"DDG\t$file\t$method\t${show(src)}\t${show(e.dst.asInstanceOf[StoredNode])}\t${clean(String.valueOf(e.property))}\n") }
  }
  cpg.call.nameExact("<operator>.raise").foreach { call =>
    val (file, method) = owner(call)
    val inTry = call.inAst.takeWhile(!_.isInstanceOf[Method]).collect { case c: ControlStructure if c.controlStructureType == "TRY" => c }.nonEmpty
    out.print(s"RAISE\t$file\t$method\t${call.id}\t$inTry\n")
  }
  out.print("END\n")
  out.close()
}
